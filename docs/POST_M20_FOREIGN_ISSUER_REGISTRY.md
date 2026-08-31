# Post-M20 — CVM foreign-issuer registry audit

## Objective

Resolve issuer jurisdiction using the official CVM foreign-company registry before defining the Brazilian-equity universe boundary.

This gate remains diagnostic only. It does not alter scoring, rankability, model routing, weights, thresholds or security eligibility.

## Official source

CVM Open Data publishes `cad_cia_estrang.csv` under **Cias Estrangeiras: Informação Cadastral**. The dataset is maintained by SEP and updated daily.

Source URL:

`https://dados.cvm.gov.br/dados/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv`

The normalized identity is taken directly from the official `CD_CVM` field:

`company_id = cvm:<CD_CVM>`

No ticker suffix, company-name inference or fuzzy matching is permitted.

## Live acceptance controls

The bounded smoke requires these canonical identities to exist in the foreign-company registry:

- `cvm:80195` — G2D Investments, Ltd.;
- `cvm:80152` — PPLA Participations Ltd.

It also requires `cvm:9512` — Petrobras — to remain absent as a negative control.

The smoke reports legal name, registration status, registration date and cancellation date exactly as supplied by the current CVM registry.

## Point-in-time rule

The downloaded CSV is a current registry-state snapshot. It is therefore marked `point_in_time_eligible = false` and cannot be retroactively used as if it described issuer jurisdiction/registration status at every historical date.

Historical eligibility requires a dated/revision-aware registry or evidence available at the historical cutoff.

## Next gate

Once the live source proves the canonical identities and current participant class, a later universe contract may distinguish Brazilian public-company equity from foreign-issuer instruments. Any exclusion must be based on this official issuer classification plus an explicit project-universe rule, not on ticker shape or the absence of a row from FCA.
