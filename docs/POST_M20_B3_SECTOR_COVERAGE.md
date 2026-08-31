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
- normalized company count;
- company count by selected sector model;
- specialized-model versus `general_corporate` fallback counts;
- specialized-model routing coverage;
- rows matching more than one specialized model rule;
- bounded samples of outside-catalog issuer codes and ambiguous company IDs.

The join ratio is deliberately **not** labeled as complete B3 equity-universe coverage. The company-catalog endpoint contains a broader population than the industry-classification workbook, while the workbook can also contain instrument-related issuer codes that do not resolve as active companies. The profiler therefore reports exactly what can be established from the two official sources without inventing a security-type classification.

`general_corporate` is the registry's intentional default model, so fallback is not treated as an error. The important quality signals are unresolved official joins and overlapping specialized routing rules.

## Gas-utility routing correction

The first live smoke exposed three companies classified by B3 as `Utilidade Pública / Gás / Gás` that matched both `utilities` and `commodities`, because the commodity model used the generic token `gas` at subsector/segment level. The registry was tightened to keep oil-and-gas commodity detection at the sector level and through more specific oil/petroleum patterns. Gas-distribution utilities now match only `utilities` while petroleum companies remain covered by the commodity rules.

## Operational smoke

`.github/workflows/b3-sector-coverage-smoke.yml` runs weekly, on demand, and on pull requests that change the classification/routing contract. It generates only `b3-sector-coverage.json` with a 14-day retention period.

The B3 classification source is a latest-state source and this profiler does not establish historical publication/revision timing. Therefore the output remains `point_in_time_eligible=false` and must not be used as historical PIT evidence.
