# M14 — Integrated Decision Model

Status: **implemented in v1.4 candidate**.

## Three separate answers

M14 formalizes the user-facing separation that has guided the architecture since the beginning:

1. **Company Quality Score** — is this structurally a good business?
2. **Investment Attractiveness Score** — is the security attractive at the current price and context?
3. **Entry Timing Score** — is this a favorable moment to initiate/add a position?

`Entry Timing Score` does **not** modify `Investment Attractiveness Score`. A low entry score can
produce `WAIT`, but it cannot turn a strong company into a weak business. Likewise, a temporary
technical setup cannot rescue poor structural quality.

## Company Quality

v1.4 combines:

- Structural Score — 65%;
- Accounting Quality — 15%;
- Governance — 12%;
- Audit Safety (`100 - AuditRisk`) — 8%.

These are hypothesis weights pending M15/M16 validation.

## Investment Attractiveness

The current deterministic hypothesis combines:

- Company Quality — 55%;
- Valuation — 25%;
- News/Event — 5%;
- Macro Context — 5%;
- Risk Safety — 4%;
- Liquidity — 3%;
- Net Lending — 3%.

The investment score is the primary **ranking score**. `ActionabilityScore` is separately exposed
as an optional current-opportunity sort key (85% investment attractiveness, 15% entry timing).
It is never presented as the company's fundamental quality.

## Data Confidence Score

M14 introduces an explicit deterministic Data Confidence Score based on:

- completeness;
- freshness;
- share of official evidence;
- consistency across sources/revisions;
- point-in-time lineage.

Missing dimensions reduce coverage. Low data confidence produces `INCONCLUSIVE`, not a fabricated
ranking.

## Gates and statuses

Statuses are:

- `VERY_ATTRACTIVE`;
- `ATTRACTIVE`;
- `WATCH`;
- `WAIT`;
- `AVOID`;
- `BLOCKED`;
- `INCONCLUSIVE`.

A critical audit event or other blocking red flag always produces `BLOCKED`, regardless of scores.
Structural, valuation and entry scores are required for a rankable integrated decision.

## Calibration

All v1.4 weights and thresholds remain hypotheses. M15 reconstructs point-in-time historical
decisions, and M16 evaluates/calibrates these assumptions with walk-forward tests. No weight should
be described as empirically optimal before those milestones.
