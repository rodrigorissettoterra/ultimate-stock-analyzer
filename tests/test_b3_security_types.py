from ultimate_stock_analyzer.universe.b3_security_types import (
    B3SecurityKind,
    classify_b3_security_specification,
    classify_b3_security_specifications,
)


def test_b3_security_taxonomy_keeps_equity_event_suffixes_in_underlying_class() -> None:
    assert classify_b3_security_specification("ON  ED  NM").kind == B3SecurityKind.COMMON_SHARE
    assert classify_b3_security_specification("PN  EJ  N1").kind == B3SecurityKind.PREFERRED_SHARE
    assert classify_b3_security_specification("PNA ATZ N1").kind == B3SecurityKind.PREFERRED_SHARE
    assert classify_b3_security_specification("UNT ED  N2").kind == B3SecurityKind.UNIT


def test_b3_security_taxonomy_does_not_promote_receipts_rights_or_bonuses() -> None:
    receipt = classify_b3_security_specification("PN REC N2")
    assert receipt.kind == B3SecurityKind.SUBSCRIPTION_RECEIPT
    assert receipt.core_equity_security is False
    assert classify_b3_security_specification("BNS ORD NM").kind == B3SecurityKind.SUBSCRIPTION_BONUS
    assert classify_b3_security_specification("DIR ORD N1").kind == B3SecurityKind.SUBSCRIPTION_RIGHT


def test_b3_security_taxonomy_separates_bdr_and_variable_royalty_title() -> None:
    assert classify_b3_security_specification("DR2 ED").kind == B3SecurityKind.BDR
    assert classify_b3_security_specification("DR3").kind == B3SecurityKind.BDR
    assert classify_b3_security_specification("TPR EJ").kind == B3SecurityKind.VARIABLE_ROYALTY_TITLE


def test_b3_security_taxonomy_unknown_fails_closed() -> None:
    decision = classify_b3_security_specification("XYZ SPECIAL")
    assert decision.kind == B3SecurityKind.OTHER_UNKNOWN
    assert decision.core_equity_security is False


def test_b3_security_taxonomy_detects_kind_changes_for_same_exact_code() -> None:
    result = classify_b3_security_specifications(("PN", "PN REC"))
    assert result.conflict is True
    assert result.coherent_kind is None
    assert result.core_equity_security is False


def test_b3_security_taxonomy_accepts_multiple_event_states_of_same_equity_kind() -> None:
    result = classify_b3_security_specifications(("ON", "ON ED NM", "ON EJ NM"))
    assert result.conflict is False
    assert result.coherent_kind == B3SecurityKind.COMMON_SHARE
    assert result.core_equity_security is True
