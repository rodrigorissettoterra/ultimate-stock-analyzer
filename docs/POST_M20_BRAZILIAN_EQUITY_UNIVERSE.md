# Post-M20 — Brazilian-company equity universe contract

## Scope

The project charter defines the research universe as Brazilian equities. Jurisdiction therefore belongs to universe eligibility, before structural scoring, and must not be encoded as a score penalty or inferred from a ticker.

This block formalizes the deterministic jurisdiction contract but does not yet wire it into the production ranking pipeline.

## Official identity sources

Two separate CVM registries are compared using the same canonical key:

1. `CVM_CAD` — `cad_cia_aberta.csv`, Brazilian public companies;
2. `CVM_FOREIGN_ISSUER_CAD` — `cad_cia_estrang.csv`, foreign issuers.

Identity is always:

`company_id = cvm:<CD_CVM>`

No ticker suffix, issuer code, legal-name inference or fuzzy matching participates in the decision.

## Eligibility states

### `ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY`

The canonical CVM identity exists in the Brazilian public-company registry and not in the foreign-issuer registry.

### `EXCLUDED_FOREIGN_ISSUER`

The canonical CVM identity exists in the foreign-issuer registry. Because the project universe is Brazilian-company equities, the issuer is outside the universe contract. This is an eligibility decision, not a negative investment opinion.

### `CONFLICTING_CVM_REGISTRY_CLASSIFICATION`

The identity exists in both registries. Eligibility fails closed until the source conflict is investigated.

### `UNRESOLVED_CVM_REGISTRY_CLASSIFICATION`

The identity exists in neither registry. Eligibility fails closed; the implementation does not infer jurisdiction from ticker or name.

## Live acceptance controls

The current-state smoke requires:

- `cvm:9512` / Petrobras -> `ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY`;
- `cvm:80152` / PPLA Participations -> `EXCLUDED_FOREIGN_ISSUER`;
- `cvm:80195` / G2D Investments -> `EXCLUDED_FOREIGN_ISSUER`.

## Point-in-time limitation

Both registry downloads are current-state snapshots for this gate. The resulting eligibility is explicitly `point_in_time_eligible = false` and cannot be reused in historical walk-forward/backtests without dated or revision-aware jurisdiction evidence.

## Next gate

The next block may integrate this contract into the **current** B3 universe/profile pipeline. That integration must:

- preserve excluded issuers in audit output;
- remove them from the Brazilian-equity ranking candidate set rather than penalizing their score;
- fail closed on unresolved/conflicting identities;
- leave historical/backtest eligibility untouched until a point-in-time source exists.
