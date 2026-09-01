# Post-M20 — ITSA Holding Accounting Contract

## Status

This block promotes the previously diagnostic ITSA (`cvm:7617`) statement evidence into
an exact **accounting contract**. It remains **not routed** and does not define a score.

Promotion is based on the merged 2021–2025 stability audit: all seven selected
statement/account-code pairs preserved the same labels in every annual DFP observed.

## Contract

`itsa_holding_cvm_v1` uses five critical concepts:

- total assets — `BPA 1` — `Ativo Total`;
- investments — `BPA 1.02.02` — `Investimentos`;
- equity — `BPP 2.03` — `Patrimônio Líquido`;
- equity-method result — `DRE 3.04.06` —
  `Resultado de Equivalência Patrimonial`;
- individual net income — `DRE 3.11` — `Lucro/Prejuízo do Período`.

Two supporting concepts preserve the investment tree without double counting:

- equity investments — `BPA 1.02.02.01` — `Participações Societárias`;
- other investments — `BPA 1.02.02.01.04` — `Outros Investimentos`.

## Extraction rules

Extraction fails closed on:

- wrong `company_id`;
- duplicate exact statement/account-code matches;
- label drift on an exact code.

An absent code is not converted to zero. It remains absent and is reflected in contract
coverage.

No fuzzy label matching or economic substitution is allowed.

## Descriptive metrics

The contract can calculate descriptive evidence from the exact extracted values:

- investments / total assets;
- equity / total assets;
- equity-method result / net income;
- equity investments / investments;
- other investments / investments.

These are **not** score formulas. No directions, weights, targets, thresholds or
recommendation effects are defined.

The investments ratio uses only parent code `1.02.02`; child rows are never added back
into the same total.

## Live validation

```bash
python scripts/itsa_holding_accounting_contract_audit.py \
  --year 2025 \
  --output itsa-holding-accounting-contract-audit.json
```

The workflow
`.github/workflows/itsa-holding-accounting-contract-audit-smoke.yml`
requires the full seven-binding 2025 contract to resolve from official CVM DFP evidence.

## Temporal boundary

The contract semantics are supported by exact schema stability from 2021 through 2025,
but the downloaded annual CVM archives remain latest-state snapshots. This does not make
them a complete revision-aware point-in-time dataset for strict historical backtesting.

## Decision boundary

A valid accounting contract permits later peer discovery and metric research. It does
**not** authorize:

- routing ITSA away from `general_corporate`;
- structural scoring;
- rankability;
- applicability-review removal;
- investment recommendations.
