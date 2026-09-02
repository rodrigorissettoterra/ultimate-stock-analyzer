# Post-M20 — Pillar 3 Prudential Numeric Layout Audit

Status: **diagnostic only; no readiness change**.

## Goal

The prior block proved that all four observed Itaú 4T24/4T25 versioned RAD PDFs contain the expected
prudential metric labels. This block inspects how `pypdf` exposes the nearby numeric layout before any
number is promoted as a metric value.

## Contract

For each versioned PDF and each target metric, the audit records only bounded evidence:

- matched metric label;
- PDF page number;
- a bounded neighboring-line context;
- nearby percent/decimal tokens.

The target metrics are Capital Principal, Nível I, Índice de Basileia and Razão de Alavancagem.
When a label occurs more than once, a context containing numeric candidates is preferred over a
non-numeric table-of-contents occurrence.

## Fail-closed boundary

Nearby numbers are candidates, not values. This block does not decide which table column belongs to
the target reference date and does not extract a numeric bank profile.

It therefore always retains:

```text
PILLAR3_NUMERIC_LAYOUT_UNPROVEN
PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN
BANK_EVIDENCE_NOT_POINT_IN_TIME
```

and keeps numeric extraction, bank PIT readiness and readiness promotion disabled.

## Next step

The inspected live layouts will define the smallest deterministic parser capable of selecting the
correct KM1/LR2 target-date values. That parser must then compare version 1 and version 2 explicitly
before any Pillar 3 metric can enter historical bank evidence.
