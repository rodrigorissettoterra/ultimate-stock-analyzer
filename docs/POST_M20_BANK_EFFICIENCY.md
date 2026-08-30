# Post-M20 bank operational efficiency evidence

## Scope

This increment adds the BCB operational efficiency ratio (IEO) to the bank-specific evidence path for fiscal periods covered by the 2025+ COSIF/IFData report-4 layout. It does not change the bank ranking threshold, source hierarchy, identity rules, or point-in-time policy.

## Official definition

The Banco Central do Brasil defines the Índice de Eficiência Operacional (IEO) as administrative expenses divided by operating result, disregarding the effects of provision expenses. Recent Financial Stability Reports use this definition and identify Cosif as the source.

For the 2025+ IFData report-4 layout, the exact prudential-conglomerate rows verified in the official 2025-12 payload for `C0080099` are:

- `141859` — Despesas Administrativas `(p)`;
- `141867` — Resultado antes da Tributação e Participações `(w) = (k) + (l) + (v)`;
- `141842` — Resultado com Perda Esperada `(f)`;
- `141860` — Resultado com Perdas Esperadas de Outras Operações `(q)`.

The implementation uses identifiers only. Names are documentary evidence and are never used for fuzzy production matching.

## Annual reconstruction

IFData DRE flows are annualized as June semester + December semester, consistent with the existing bank contract. March and September are not added to those semesters.

For 2025+:

```text
administrative_expense = -(Jun_141859 + Dec_141859)
operating_result_ex_provisions =
    (Jun_141867 + Dec_141867)
    - (Jun_141842 + Dec_141842)
    - (Jun_141860 + Dec_141860)

efficiency_ratio = administrative_expense / operating_result_ex_provisions
```

The raw expense must be non-positive and the reconstructed denominator must be positive. If a required component is absent or fails those sign/denominator checks, the affected value remains `UNKNOWN` (`None`).

## Historical boundary

The report-4 accounting structure changed at the 2025 COSIF transition. This increment deliberately does not infer or fuzzy-map a pre-2025 efficiency formula. Pre-2025 `efficiency_ratio` remains `UNKNOWN` until the exact historical official-payload account contract is independently verified.

## Point-in-time treatment

The IFData API exposes latest-state historical observations without a revision timeline. Therefore the normalized bank profile continues to use `point_in_time_eligible=false` and cannot be silently treated as strict PIT evidence in historical backtests.

## Structural coverage

Under `banks_v0.6`, `efficiency_ratio` contributes 70% of the 15% efficiency category, or 10.5 percentage points of structural coverage. Combined with the previously verified 45% subset, the bounded verified set reaches 55.5%, still below the unchanged 65% rankability gate. The bank therefore remains non-rankable until additional evidence is proven.

## Sources

- Banco Central do Brasil, *Relatório de Estabilidade Financeira – Abril 2025*, operational-efficiency methodology and Cosif source.
- Banco Central do Brasil, *Relatório de Estabilidade Financeira – Maio 2026*, current IEO definition.
- Banco Central do Brasil, IFData official report-4 payload for prudential conglomerates, 2025-12.
