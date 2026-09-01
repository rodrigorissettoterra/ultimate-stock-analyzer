from __future__ import annotations

import argparse
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.normalization.cvm import (
    attach_document_metadata,
    normalize_statement,
    point_in_time_lines,
)

TARGET_CVM_CODE = 26824
TARGET_REFERENCE_DATE = "2024-12-31"
TARGET_VERSION = 1


def _natural_key_mask(frame: pd.DataFrame) -> pd.Series:
    cvm_code = pd.to_numeric(frame["CD_CVM"], errors="coerce").astype("Int64")
    reference_date = pd.to_datetime(frame["DT_REFER"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    version = pd.to_numeric(frame["VERSAO"], errors="coerce").astype("Int64")
    return (
        (cvm_code == TARGET_CVM_CODE)
        & (reference_date == TARGET_REFERENCE_DATE)
        & (version == TARGET_VERSION)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live regression for ambiguous CVM natural-key filing metadata."
    )
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument(
        "--output",
        default="cvm-ambiguous-filing-metadata-smoke.json",
    )
    args = parser.parse_args()

    collector = CVMCollector(timeout_seconds=180.0)
    archive = collector.download_zip("DFP", args.year)
    metadata = collector.read_csv(archive, f"dfp_cia_aberta_{args.year}.csv")

    metadata_target = metadata.loc[_natural_key_mask(metadata)].copy()
    receipt_dates = sorted(
        {
            str(value).strip()
            for value in metadata_target["DT_RECEB"]
            if not pd.isna(value) and str(value).strip()
        }
    )
    document_ids = sorted(
        {
            int(value)
            for value in pd.to_numeric(
                metadata_target["ID_DOC"], errors="coerce"
            ).dropna()
        }
    )
    if len(metadata_target) != 2 or len(receipt_dates) != 2 or len(document_ids) != 2:
        raise AssertionError(
            "official ambiguity control changed; review the CVM metadata contract"
        )

    matching_files: list[str] = []
    ambiguous_statement_rows = 0
    control_rows_with_publication_time = 0
    ambiguous_pit_eligible_lines = 0
    warning_count = 0
    collected_at = datetime.now(UTC)

    for filename in collector.list_csv_files(archive):
        lower = filename.lower()
        if not lower.startswith("dfp_cia_aberta_") or "_con_" not in lower:
            continue
        frame = collector.read_csv(archive, filename)
        required = {"CD_CVM", "DT_REFER", "VERSAO", "CD_CONTA", "VL_CONTA"}
        if not required.issubset(frame.columns):
            continue
        target_mask = _natural_key_mask(frame)
        if not target_mask.any():
            continue

        matching_files.append(filename)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            joined = attach_document_metadata(frame, metadata)
        warning_count += sum(
            issubclass(item.category, RuntimeWarning) for item in caught
        )

        joined_target = joined.loc[target_mask].copy()
        ambiguous_statement_rows += len(joined_target)
        if "ID_DOC" not in joined_target.columns or "DT_RECEB" not in joined_target.columns:
            raise AssertionError("fallback metadata columns were not attached")
        if joined_target["ID_DOC"].notna().any():
            raise AssertionError("ambiguous natural key received an inferred document id")
        if joined_target["DT_RECEB"].notna().any():
            raise AssertionError("ambiguous natural key received an inferred receipt time")

        controls = joined.loc[~target_mask]
        control_rows_with_publication_time += int(controls["DT_RECEB"].notna().sum())

        lines = normalize_statement(
            joined_target,
            document_type="DFP",
            statement="SMOKE",
            collected_at=collected_at,
            source_document=filename,
        )
        if any(line.available_from is not None for line in lines):
            raise AssertionError("ambiguous filing became point-in-time eligible")
        ambiguous_pit_eligible_lines += len(
            point_in_time_lines(lines, as_of=collected_at)
        )

    if not matching_files or ambiguous_statement_rows == 0:
        raise AssertionError("official ambiguous filing was absent from DFP statement members")
    if control_rows_with_publication_time == 0:
        raise AssertionError("unambiguous control rows lost publication metadata")
    if ambiguous_pit_eligible_lines != 0:
        raise AssertionError("ambiguous filing leaked into the point-in-time snapshot")
    if warning_count == 0:
        raise AssertionError("ambiguous natural-key metadata was not surfaced as a warning")

    payload = {
        "effect": "normalization_regression_only",
        "source": "CVM_DFP_OFFICIAL_ARCHIVE",
        "year": args.year,
        "natural_key": {
            "CD_CVM": TARGET_CVM_CODE,
            "DT_REFER": TARGET_REFERENCE_DATE,
            "VERSAO": TARGET_VERSION,
        },
        "official_metadata_row_count": len(metadata_target),
        "official_distinct_receipt_time_count": len(receipt_dates),
        "official_distinct_document_id_count": len(document_ids),
        "matching_statement_file_count": len(matching_files),
        "ambiguous_statement_row_count": ambiguous_statement_rows,
        "ambiguous_pit_eligible_line_count": ambiguous_pit_eligible_lines,
        "control_rows_with_publication_time": control_rows_with_publication_time,
        "runtime_warning_count": warning_count,
        "status": "PASS",
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
