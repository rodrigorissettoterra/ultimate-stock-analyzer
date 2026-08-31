from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import SecurityRecord
from ultimate_stock_analyzer.scoring.security_universe_audit import audit_security_types


def _security(
    ticker: str,
    *,
    company_id: str,
    security_type: str,
    reference_date: date,
    version: int,
) -> SecurityRecord:
    return SecurityRecord(
        company_id=company_id,
        ticker=ticker,
        isin="BRTEST000001",
        security_type=security_type,
        market="Bolsa",
        administrator="B3",
        reference_date=reference_date,
        version=version,
        available_from=datetime(2026, 3, 1, tzinfo=UTC),
        collected_at=datetime(2026, 8, 31, tzinfo=UTC),
        source_document="fca.csv",
    )


def test_security_type_audit_preserves_exact_observed_fields() -> None:
    report = audit_security_types(
        [
            _security(
                "PETR4",
                company_id="cvm:9512",
                security_type="Ações Preferenciais",
                reference_date=date(2025, 12, 31),
                version=7,
            ),
            _security(
                "G2DI33",
                company_id="cvm:80195",
                security_type="Brazilian Depositary Receipts - BDR",
                reference_date=date(2025, 12, 31),
                version=2,
            ),
        ],
        tickers=("g2di33", "PETR4", "PPLA11"),
    )

    assert report.requested_tickers == ("G2DI33", "PETR4", "PPLA11")
    assert report.found_tickers == ("G2DI33", "PETR4")
    assert report.missing_tickers == ("PPLA11",)
    assert report.latest_rows[0].company_id == "cvm:80195"
    assert report.latest_rows[0].security_type == "Brazilian Depositary Receipts - BDR"
    assert report.latest_rows[1].security_type == "Ações Preferenciais"


def test_security_type_audit_chooses_latest_reference_and_version() -> None:
    report = audit_security_types(
        [
            _security(
                "PETR4",
                company_id="cvm:9512",
                security_type="old",
                reference_date=date(2024, 12, 31),
                version=99,
            ),
            _security(
                "PETR4",
                company_id="cvm:9512",
                security_type="new-v1",
                reference_date=date(2025, 12, 31),
                version=1,
            ),
            _security(
                "PETR4",
                company_id="cvm:9512",
                security_type="new-v2",
                reference_date=date(2025, 12, 31),
                version=2,
            ),
        ],
        tickers=("PETR4",),
    )

    assert report.latest_rows[0].security_type == "new-v2"
    assert report.latest_rows[0].version == 2
