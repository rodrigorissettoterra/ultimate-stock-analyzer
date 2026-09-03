from ultimate_stock_analyzer.backtesting.bank_pit_source_routing import (
    BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED,
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED,
    BANK_MODEL_PIT_COVERAGE_INCOMPLETE,
    BANK_SCOPE_ALIGNMENT_UNPROVEN,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    audit_bank_pit_source_routing,
)


def test_bank_critical_contract_routes_are_complete_and_fail_closed() -> None:
    audit = audit_bank_pit_source_routing()
    routes = {item.input_name: item for item in audit.critical_routes}

    assert routes["basel_ratio"].status == "validated_observed_pit"
    assert routes["tier1_ratio"].status == "validated_observed_pit"
    assert routes["total_assets"].status == "timestamped_candidate_unaligned"
    assert routes["annual_net_income"].evidence_field == "net_income_consolidated"
    assert routes["gross_credit_portfolio"].status == "latest_state_non_pit"
    assert routes["annual_credit_loss_result"].status == "latest_state_non_pit"
    assert audit.proven_pit_critical_coverage == 0.2
    assert audit.timestamped_candidate_or_better_critical_coverage == 0.7
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed

    assert {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        BANK_SCOPE_ALIGNMENT_UNPROVEN,
        BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED,
        BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED,
        BANK_MODEL_PIT_COVERAGE_INCOMPLETE,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    }.issubset(audit.blockers)


def test_bank_model_weight_inventory_identifies_proven_and_candidate_share() -> None:
    audit = audit_bank_pit_source_routing()
    metrics = {item.metric: item for item in audit.model_metric_routes}

    assert len(metrics) == 16
    assert abs(sum(item.model_weight for item in metrics.values()) - 1.0) < 1e-12
    assert audit.proven_pit_model_weight == 0.16
    assert abs(audit.timestamped_candidate_or_better_model_weight - 0.405) < 1e-12
    assert metrics["basel_ratio"].status == "validated_observed_pit"
    assert metrics["tier1_ratio"].status == "validated_observed_pit"
    assert metrics["roe"].status == "timestamped_candidate_unaligned"
    assert metrics["net_interest_margin"].status == "unresolved"
    assert metrics["efficiency_ratio"].status == "latest_state_non_pit"
    assert metrics["dividend_regularity"].status == "outside_bank_accounting_pit_audit"


def test_supporting_prudential_inputs_are_observed_pit_routes() -> None:
    audit = audit_bank_pit_source_routing()
    routes = {item.input_name: item for item in audit.supporting_routes}

    assert set(routes) == {"core_equity_tier1_ratio", "leverage_ratio"}
    assert all(item.status == "validated_observed_pit" for item in routes.values())
