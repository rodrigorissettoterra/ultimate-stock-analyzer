# Post-M20 — B3 sector/model coverage profiler

## Purpose

Measure, with current official B3 classification data, how completely the listed-company classification chain reaches the sector-model registry. This is an empirical coverage gate, not a new scoring model.

## Source and identity

The profiler reuses the existing B3 industry-classification collector. The official classification workbook is joined to the official listed-company catalog through the exact B3 issuer code, which in turn provides CVM code and CNPJ. Normalized identity remains `company_id = cvm:<CD_CVM>`; no ticker/name/fuzzy matching is introduced.

The downloaded workbook and company catalog are processed in memory and are not committed or uploaded as artifacts. The workflow artifact contains only aggregate counts plus bounded public issuer/company identifiers for unresolved or ambiguous cases.

## Measures

The manifest reports:

- number of classification rows in the official workbook;
- identity-mapped and identity-unmapped rows;
- exact identity coverage ratio;
- normalized company count;
- company count by selected sector model;
- specialized-model versus `general_corporate` fallback counts;
- specialized-model routing coverage;
- rows matching more than one specialized model rule;
- bounded samples of unmapped issuer codes and ambiguous company IDs.

`general_corporate` is the registry's intentional default model, so fallback is not treated as an error. The important quality signals are unresolved B3→CVM identity and overlapping specialized routing rules.

## Operational smoke

`.github/workflows/b3-sector-coverage-smoke.yml` runs weekly, on demand, and on pull requests that change the classification/routing contract. It generates only `b3-sector-coverage.json` with a 14-day retention period.

The B3 classification source is a latest-state source and this profiler does not establish historical publication/revision timing. Therefore the output remains `point_in_time_eligible=false` and must not be used as historical PIT evidence.
