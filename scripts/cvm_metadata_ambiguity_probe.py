from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ultimate_stock_analyzer.collectors.cvm import CVMCollector


def _normalized_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


def _normalized_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _string_values(series: pd.Series) -> list[str]:
    values = {
        str(value).strip()
        for value in series
        if not pd.isna(value) and str(value).strip()
    }
    return sorted(values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe one ambiguous CVM DFP metadata natural key."
    )
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--cvm-code", type=int, default=26824)
    parser.add_argument("--reference-date", default="2024-12-31")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--output", default="cvm-metadata-ambiguity-probe.json")
    args = parser.parse_args()

    collector = CVMCollector(timeout_seconds=180.0)
    archive = collector.download_zip("DFP", args.year)
    metadata = collector.read_csv(archive, f"dfp_cia_aberta_{args.year}.csv")

    cvm_codes = _normalized_int(metadata["CD_CVM"])
    reference_dates = _normalized_date(metadata["DT_REFER"])
    versions = _normalized_int(metadata["VERSAO"])
    matches = metadata.loc[
        (cvm_codes == args.cvm_code)
        & (reference_dates == args.reference_date)
        & (versions == args.version)
    ].copy()
    if len(matches) < 2:
        raise RuntimeError(
            "probe expected an ambiguous natural key with at least two metadata rows; "
            f"found={len(matches)}"
        )

    differing_fields: dict[str, dict[str, object]] = {}
    consensus_fields: dict[str, object] = {}
    for column in matches.columns:
        values = _string_values(matches[column])
        if len(values) > 1:
            differing_fields[str(column)] = {
                "distinct_non_null_count": len(values),
                "values": values[:10],
            }
        elif len(values) == 1:
            consensus_fields[str(column)] = values[0]
        else:
            consensus_fields[str(column)] = None

    payload = {
        "effect": "diagnostic_only",
        "source": "CVM_DFP_OFFICIAL_ARCHIVE",
        "year": args.year,
        "natural_key": {
            "CD_CVM": args.cvm_code,
            "DT_REFER": args.reference_date,
            "VERSAO": args.version,
        },
        "row_count": len(matches),
        "metadata_columns": [str(column) for column in matches.columns],
        "differing_fields": differing_fields,
        "consensus_metadata": {
            field: consensus_fields.get(field)
            for field in ("DT_RECEB", "ID_DOC", "LINK_DOC")
            if field in matches.columns
        },
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
