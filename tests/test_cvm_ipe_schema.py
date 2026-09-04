import io
import zipfile

import pytest

from ultimate_stock_analyzer.collectors.cvm_ipe import (
    CVM_IPE_REQUIRED_COLUMNS,
    inspect_cvm_ipe_zip_columns,
)


def _zip_with_columns(columns: tuple[str, ...]) -> bytes:
    payload = (";".join(columns) + "\n").encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ipe.csv", payload)
    return output.getvalue()


def test_inspect_cvm_ipe_zip_columns_preserves_exact_order() -> None:
    columns = tuple(sorted(CVM_IPE_REQUIRED_COLUMNS))
    observed = inspect_cvm_ipe_zip_columns(_zip_with_columns(columns))

    assert observed == columns


def test_inspect_cvm_ipe_zip_columns_preserves_optional_status() -> None:
    columns = (*tuple(sorted(CVM_IPE_REQUIRED_COLUMNS)), "Status")
    observed = inspect_cvm_ipe_zip_columns(_zip_with_columns(columns))

    assert observed[-1] == "Status"
    assert set(CVM_IPE_REQUIRED_COLUMNS).issubset(observed)


def test_inspect_cvm_ipe_zip_columns_preserves_raw_optional_header_text() -> None:
    columns = (*tuple(sorted(CVM_IPE_REQUIRED_COLUMNS)), " Campo_Extra ")
    observed = inspect_cvm_ipe_zip_columns(_zip_with_columns(columns))

    assert observed[-1] == " Campo_Extra "


def test_inspect_cvm_ipe_zip_columns_fails_closed_on_missing_required_field() -> None:
    columns = tuple(
        column
        for column in sorted(CVM_IPE_REQUIRED_COLUMNS)
        if column != "Protocolo_Entrega"
    )

    with pytest.raises(ValueError, match="Protocolo_Entrega"):
        inspect_cvm_ipe_zip_columns(_zip_with_columns(columns))


def test_inspect_cvm_ipe_zip_columns_fails_closed_on_duplicate_header() -> None:
    columns = (*tuple(sorted(CVM_IPE_REQUIRED_COLUMNS)), "Versao")

    with pytest.raises(ValueError, match="duplicate columns"):
        inspect_cvm_ipe_zip_columns(_zip_with_columns(columns))
