# Post-M20 — ITSA Holding Schema Stability Audit

## Status

Diagnostic only. This block continues the unresolved structural-applicability review for
ITSA (`cvm:7617`) after the earlier holding-model CVM data-contract audit.

It does **not** create a holding score, peer set, routing rule, rankability change,
recommendation change, valuation rule or applicability-registry resolution.

## Evidence basis

The prior official CVM DFP 2025 holding audit showed that ITSA is economically dominated
by investment holdings rather than ordinary operating assets:

- total assets: approximately R$ 94.773 billion;
- `Investimentos` (`BPA 1.02.02`): approximately R$ 88.495 billion;
- `Resultado de Equivalência Patrimonial` (`DRE 3.04.06`):
  approximately R$ 17.291 billion;
- individual net income (`DRE 3.11`): approximately R$ 16.487 billion.

The same audit also exposed nested investment rows. Therefore account-name matching or
summing every investment-like row would risk parent/child double counting.

## Objective

Before any normative ITSA accounting contract is proposed, verify whether the exact
statement/account-code structure observed in 2025 is stable across DFP 2021–2025.

The audit follows seven concepts:

1. total assets — `BPA 1`;
2. investments parent — `BPA 1.02.02`;
3. equity investments — `BPA 1.02.02.01`;
4. other investments — `BPA 1.02.02.01.04`;
5. equity — `BPP 2.03`;
6. equity-method result — `DRE 3.04.06`;
7. individual net income — `DRE 3.11`.

The codes are explicit candidates from the prior 2025 evidence. Labels are **not**
hardcoded as semantic truth: the live audit reads each baseline label directly from the
exact ITSA 2025 DFP statement tree, then compares that same statement + account code across
the historical window.

## Fail-closed rules

- exact issuer identity is `cvm:7617` / `CD_CVM=7617`;
- exact statement + account code is required;
- the 2025 baseline code must resolve exactly once;
- an absent historical code remains missing/UNKNOWN;
- any historical label drift is surfaced for review;
- no semantic remapping by similar account name is permitted;
- nested investment rows remain separate evidence and are never summed together.

## Descriptive economic evidence

For every year, the report publishes the exact values available for the seven concepts and
the following descriptive ratios:

- investments / total assets;
- equity / total assets;
- equity-method result / net income;
- equity investments / investments;
- other investments / investments.

The investments/assets ratio uses only the parent code `1.02.02`. Child accounts are
reported separately so the audit cannot double count the investment tree.

These ratios are evidence only. No threshold in this block creates a score or model rule.

## Temporal boundary

Each annual archive is the current latest-state CVM DFP download for that fiscal year. It
is useful for schema stability and economic-contract discovery but is not claimed to be a
complete revision-aware point-in-time dataset for historical backtesting.

## Live smoke

```bash
python scripts/itsa_holding_schema_stability_audit.py \
  --start-year 2021 \
  --end-year 2025 \
  --baseline-year 2025 \
  --output itsa-holding-schema-stability-audit.json
```

The workflow
`.github/workflows/itsa-holding-schema-stability-audit-smoke.yml`
publishes the JSON artifact for inspection.

## Decision boundary

A fully stable core schema would only justify the next diagnostic step: evaluating a
normative ITSA holding accounting contract and economically comparable peer/ranking
strategy. It would **not**, by itself, authorize routing or scoring.
