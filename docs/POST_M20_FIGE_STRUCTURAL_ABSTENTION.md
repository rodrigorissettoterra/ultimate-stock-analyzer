# Post-M20 — FIGE Structural Abstention Routing

## Status

This block resolves FIGE's inappropriate `general_corporate` structural fallback without
inventing a score that the available evidence cannot support.

It follows three completed evidence blocks:

1. FIGE-specific CVM accounting contract;
2. 2021-2025 economic metric audit and metric selection;
3. current-B3 comparable-peer discovery.

The peer-discovery artifact found no second eligible issuer in FIGE's exact B3 segment.
The other 19 issuers in the same subsector are banks and already belong to the specialized
prudential `banks` model. The cross-sectional peer minimum therefore remains unreachable
without mixing economically incompatible institutions.

## Decision

FIGE is routed to `financial_non_prudential_abstain` when the current B3 segment is
`Outros Intermediarios Financeiros` (accent normalization is handled by the existing
registry matcher).

The model config is intentionally empty:

- no metric rules;
- no categories;
- no directions;
- no targets/tolerances;
- no weights;
- no score thresholds.

This uses the existing `StructuralScoringEngine` fail-closed behavior instead of adding a
new scoring formula. An empty structural model yields:

- structural score `50.0` (neutral placeholder);
- data coverage `0.0`;
- confidence `0.0`;
- `rankable=false`;
- no score categories;
- `LOW_STRUCTURAL_DATA_COVERAGE`;
- `LOW_STRUCTURAL_CONFIDENCE`;
- `NO_STRUCTURAL_DATA`.

The neutral numeric placeholder must not be interpreted as an investment-quality score.
Rankability/confidence are the decision-bearing fields.

## Why routing by segment is acceptable

The current live B3 peer-discovery artifact showed FIGE as the only eligible company in
`Financeiro / Intermediários Financeiros / Outros Intermediarios Financeiros`.

The routing regression reconstructs a pre-change registry by removing only the new
abstention definition and compares every current eligible B3 company before versus after.
The live gate requires exactly one model-selection delta: `cvm:6041` from
`general_corporate` to `financial_non_prudential_abstain`.

Any future eligible issuer entering the same segment will make that invariant fail and
force explicit review before the current routing is silently generalized.

## Corporate-metric isolation

The regression sends FIGE a full set of general-corporate metrics and then changes those
values by orders of magnitude. The abstention output must remain identical. This proves
that industrial/corporate metrics cannot leak back into FIGE merely because those fields
are present upstream.

## Applicability registry

`b3_structural_applicability_reviews_v0.2.json` remains as historical evidence of the
unresolved state before this routing decision.

The current registry becomes `b3_structural_applicability_reviews_v0.3.json` and contains
only the still-unresolved B100 and ITSA cases. FIGE is removed because it is no longer on
the `general_corporate` fallback; removal does not mean a positive score model was created.
It means the reviewed model-applicability problem was resolved by explicit abstention.

## Recommendation engine non-effect

The current `AnalyzerService` recommendation path uses the separate general
`ScoringEngine`. This block changes structural sector routing only. It does not change the
final recommendation engine, final-score weights, valuation, entry, news, lending, macro,
risk, liquidity or recommendation thresholds.

## Historical backtest boundary

No historical routing backtest is performed in this block. B3 industry classification in
the project is a current-state snapshot and explicitly not point-in-time eligible.
Retroactively applying today's FIGE segment to historical dates would create look-ahead
bias rather than validate the model.

The regression artifact records `historical_backtest_executed=false` with this reason.
Future historical model-routing tests require revision-aware sector evidence or another
PIT-safe classification contract.

## Live regression

Run:

```bash
python scripts/fige_structural_abstention_regression.py \
  --output fige-structural-abstention-regression.json
```

The gate fails unless all of the following remain true:

- current eligible routing delta is exactly FIGE;
- FIGE was previously on `general_corporate` fallback;
- FIGE now routes to `financial_non_prudential_abstain`;
- no other current eligible company routes to that model;
- no specialized-model ambiguity is introduced;
- FIGE is absent from the current applicability-review registry;
- structural score is neutral with zero evidence/confidence and non-rankable;
- corporate metric probes cannot alter the abstention result.

Transient B3/CVM registry network failures should be rerun on the same SHA. Do not weaken
routing or source-validation rules to make external infrastructure failures green.
