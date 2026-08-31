# Post-M20 — B3 sector/model coverage profiler

## Purpose

Measure, with current official B3 classification data, how completely the industry-classification chain reaches the sector-model registry. This is an empirical coverage gate, not a new scoring model.

## Source and identity

The profiler reuses the existing B3 industry-classification collector. The official classification workbook is joined to the official company catalog through the exact B3 issuer code, which in turn provides CVM code and CNPJ. Normalized identity remains `company_id = cvm:<CD_CVM>`; no ticker/name/fuzzy matching is introduced.

The downloaded workbook and company catalog are processed in memory and are not committed or uploaded as artifacts. The workflow artifact contains only aggregate counts plus bounded public issuer/company identifiers for unresolved or ambiguous cases.

## Measures

The manifest reports:

- number of unique issuer rows in the official classification workbook;
- workbook rows that resolve to an active official company-catalog identity;
- workbook rows outside that active company catalog;
- the workbook-to-company-catalog join coverage ratio;
- verified non-equity/non-exchange-equity exclusions;
- still-unresolved outside-catalog issuer rows;
- identity coverage after only the verified exclusions are removed from the classification denominator;
- normalized company count;
- company count by selected sector model;
- specialized-model versus `general_corporate` fallback counts;
- `general_corporate` fallback distribution by sector and subsector;
- specialized-model routing coverage;
- rows matching more than one specialized model rule;
- bounded samples of outside-catalog issuer codes and ambiguous company IDs.

The raw join ratio is deliberately **not** labeled as complete B3 equity-universe coverage. The company-catalog endpoint contains a broader population than the industry-classification workbook, while the workbook can also contain instrument-related issuer codes that do not resolve as active companies.

`equity_candidate_identity_coverage` removes only issuer rows present in the audited exclusion registry. It answers whether the remaining classification rows resolve to the active company catalog; it still does **not** establish a complete B3 equity-universe denominator.

`general_corporate` is the registry's intentional default model, so fallback is not treated as an error. Its sector/subsector distribution is reported to support an economic review of whether any structurally different business should receive a specialized model.

## Audited outside-catalog rows — 2026-08-31

The live smoke for PR #52 reported five industry-classification issuer codes outside the active company catalog: `CTBA`, `MCRJ`, `PLSC`, `PMSP`, and `RBRA`. They were reviewed against B3 evidence and are not repaired through name/ticker/fuzzy identity matching.

| Issuer code | Classification for this equity-universe gate | Official evidence |
| --- | --- | --- |
| `CTBA` | CEPAC; exclude from company-share identity denominator | B3 negotiable-securities page identifies `CTBA11B` as CEPAC issued by Prefeitura Municipal de Curitiba. |
| `MCRJ` | CEPAC; exclude from company-share identity denominator | B3 negotiable-securities page identifies `MCRJ11B` as CEPAC issued by Município do Rio de Janeiro. |
| `PMSP` | CEPAC; exclude from company-share identity denominator | B3 negotiable-securities page identifies `PMSP11B`, `PMSP12B` and `PMSP13B` as CEPAC certificates. |
| `PLSC` | Securitization-receivables issuer code outside the active equity company catalog | B3 ISIN registry identifies `PLSC` securities as CRI issued by Polo Capital Securitizadora S.A. |
| `RBRA` | Securitization-receivables issuer code outside the active equity company catalog | Current B3 disclosures use `RBRA` for OPEA Securitizadora CRI/CRA securities; B3 ISIN records also identify the issuer code. |

The machine-readable evidence registry is `config/universe/b3_non_equity_issuer_exclusions_v0.1.json`. Entries must contain explicit B3 evidence URLs. A code is considered verified only when it is both outside the active company catalog in the live collection **and** present in that reviewed registry. Any newly observed outside-catalog code remains unresolved and visible in the smoke artifact.

This registry is current-state evidence only. It must not be reused as historical point-in-time membership evidence.

## Gas-utility routing correction

The first live smoke exposed three companies classified by B3 as `Utilidade Pública / Gás / Gás` that matched both `utilities` and `commodities`, because the commodity model used the generic token `gas` at subsector/segment level. The registry was tightened to keep oil-and-gas commodity detection at the sector level and through more specific oil/petroleum patterns. Gas-distribution utilities now match only `utilities` while petroleum companies remain covered by the commodity rules.

## Operational smoke

`.github/workflows/b3-sector-coverage-smoke.yml` runs weekly, on demand, and on pull requests that change the classification/routing/equity-universe audit contract. It generates only `b3-sector-coverage.json` with a 14-day retention period.

The B3 classification source is a latest-state source and this profiler does not establish historical publication/revision timing. Therefore the output remains `point_in_time_eligible=false` and must not be used as historical PIT evidence.
