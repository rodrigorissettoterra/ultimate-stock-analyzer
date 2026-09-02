import pytest

from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    READY_COMPLETE_FACTOR,
    SUPPORTED_LABEL_FACTOR_CONFLICT,
    SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR,
    UNSUPPORTED_STOCK_EVENT_LABEL,
    UNSUPPORTED_SUBSCRIPTION_RIGHTS,
    B3CorporateActionsContractAuditor,
)
from ultimate_stock_analyzer.collectors.b3_dividends import B3DividendCollector


def test_b3_supplement_payload_accepts_root_dict() -> None:
    payload = {"stockDividends": []}

    assert B3DividendCollector.normalize_payload_shape(payload) is payload


def test_b3_supplement_payload_unwraps_single_root_object() -> None:
    payload = {"stockDividends": [], "subscriptions": []}

    assert B3DividendCollector.normalize_payload_shape([payload]) is payload


@pytest.mark.parametrize("payload", [[], [{}, {}], ["invalid"], "invalid", None])
def test_b3_supplement_payload_rejects_ambiguous_shapes(payload: object) -> None:
    with pytest.raises(TypeError, match="unexpected B3 corporate-actions response"):
        B3DividendCollector.normalize_payload_shape(payload)


def test_complete_factor_is_the_only_ready_conversion_path() -> None:
    payload = {
        "stockDividends": [
            {
                "assetIssued": "ITSA4",
                "factor": "1,02",
                "completeFactor": "1,02 para 1",
                "approvedOn": "15/12/2025",
                "isinCode": "BRITSAACNPR7",
                "label": "BONIFICAÇÃO",
                "lastDatePrior": "18/12/2025",
                "remarks": "",
            }
        ],
        "subscriptions": [],
    }

    audit = B3CorporateActionsContractAuditor.audit_payload(
        "itsa",
        payload,
        source_url="https://example.invalid/source",
    )

    record = audit.stock_actions[0]
    assert record.normalized_label == "BONIFICACAO"
    assert record.ratio_new_per_old == 1.02
    assert record.factor_matches_complete_factor is True
    assert record.conversion_status == READY_COMPLETE_FACTOR
    assert audit.blockers == ()


def test_raw_factor_without_complete_factor_fails_closed() -> None:
    payload = {
        "stockDividends": [
            {
                "assetIssued": "TEST3",
                "factor": "2,000000",
                "label": "DESDOBRAMENTO",
                "lastDatePrior": "10/01/2025",
            }
        ],
        "subscriptions": [],
    }

    audit = B3CorporateActionsContractAuditor.audit_payload(
        "test",
        payload,
        source_url="https://example.invalid/source",
    )

    record = audit.stock_actions[0]
    assert record.ratio_new_per_old is None
    assert record.conversion_status == SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR
    assert SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR in audit.blockers


def test_factor_conflict_blocks_conversion() -> None:
    payload = {
        "stockDividends": [
            {
                "assetIssued": "TEST3",
                "factor": "2",
                "completeFactor": "3 para 1",
                "label": "DESDOBRAMENTO",
                "lastDatePrior": "10/01/2025",
            }
        ],
        "subscriptions": [],
    }

    audit = B3CorporateActionsContractAuditor.audit_payload(
        "test",
        payload,
        source_url="https://example.invalid/source",
    )

    record = audit.stock_actions[0]
    assert record.factor_matches_complete_factor is False
    assert record.ratio_new_per_old is None
    assert record.conversion_status == SUPPORTED_LABEL_FACTOR_CONFLICT


def test_unknown_stock_event_label_is_not_silently_converted() -> None:
    payload = {
        "stockDividends": [
            {
                "assetIssued": "TEST3",
                "factor": "1,5",
                "completeFactor": "1,5 para 1",
                "label": "EVENTO ESPECIAL",
                "lastDatePrior": "10/01/2025",
            }
        ],
        "subscriptions": [],
    }

    audit = B3CorporateActionsContractAuditor.audit_payload(
        "test",
        payload,
        source_url="https://example.invalid/source",
    )

    record = audit.stock_actions[0]
    assert record.supported_label is False
    assert record.ratio_new_per_old is None
    assert record.conversion_status == UNSUPPORTED_STOCK_EVENT_LABEL


def test_subscription_rights_are_explicit_blockers() -> None:
    payload = {
        "stockDividends": [],
        "subscriptions": [
            {
                "assetIssued": "TEST3",
                "percentage": "10,0",
                "priceUnit": "5,25",
                "approvedOn": "01/02/2025",
                "lastDatePrior": "05/02/2025",
                "subscriptionDate": "20/02/2025",
                "tradingPeriod": "06/02/2025 a 18/02/2025",
                "label": "SUBSCRICAO",
            }
        ],
    }

    audit = B3CorporateActionsContractAuditor.audit_payload(
        "test",
        payload,
        source_url="https://example.invalid/source",
    )

    assert len(audit.subscriptions) == 1
    assert audit.subscriptions[0].status == UNSUPPORTED_SUBSCRIPTION_RIGHTS
    assert audit.subscriptions[0].percentage == 10.0
    assert audit.subscriptions[0].price_unit == 5.25
    assert UNSUPPORTED_SUBSCRIPTION_RIGHTS in audit.blockers


def test_stock_and_subscription_payloads_must_be_lists() -> None:
    with pytest.raises(TypeError, match="B3 stockDividends must be a list"):
        B3CorporateActionsContractAuditor.audit_payload(
            "test",
            {"stockDividends": {}, "subscriptions": []},
            source_url="https://example.invalid/source",
        )
