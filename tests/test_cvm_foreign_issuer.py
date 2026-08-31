from datetime import UTC, date, datetime

import pandas as pd
import pytest

from ultimate_stock_analyzer.collectors.cvm_foreign import CVMForeignIssuerCollector


def test_foreign_issuer_registry_normalizes_canonical_cvm_identity() -> None:
    frame = pd.DataFrame(
        [
            {
                "CD_CVM": 80195,
                "DENOM_SOCIAL": "G2D INVESTMENTS, LTD.",
                "SIT": "CANCELADO",
                "DT_REG": "2021-05-13",
                "DT_CANCEL": "2021-12-09",
            },
            {
                "CD_CVM": 80152,
                "DENOM_SOCIAL": "PPLA PARTICIPATIONS LTD.",
                "SIT": "CANCELADO",
                "DT_REG": "2012-04-24",
                "DT_CANCEL": "2021-12-09",
            },
        ]
    )
    collected_at = datetime(2026, 8, 31, tzinfo=UTC)

    records = CVMForeignIssuerCollector().normalize(frame, collected_at=collected_at)

    assert [record.company_id for record in records] == ["cvm:80152", "cvm:80195"]
    assert records[0].legal_name == "PPLA PARTICIPATIONS LTD."
    assert records[0].registration_date == date(2012, 4, 24)
    assert records[0].cancellation_date == date(2021, 12, 9)
    assert records[1].source == "CVM_FOREIGN_ISSUER_CAD"


def test_foreign_issuer_registry_fails_closed_on_unknown_schema() -> None:
    frame = pd.DataFrame([{"name": "G2D", "code": 80195}])

    with pytest.raises(ValueError, match="missing required column"):
        CVMForeignIssuerCollector().normalize(
            frame,
            collected_at=datetime(2026, 8, 31, tzinfo=UTC),
        )
