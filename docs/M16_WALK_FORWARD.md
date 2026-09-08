# M16 — Walk-Forward Calibration

Status: **implemented**.

M16 provides a conservative framework for testing whether small changes to M14's hypothesis
weights improve forward ranking power out of sample.

## No test-set optimization

For each fold:

1. candidate weights are evaluated only on the historical training window;
2. a training observation is usable only when its forward outcome would already have been known
   before the test window begins;
3. the winning training candidate is frozen;
4. only then is it evaluated on the untouched test window;
5. the same test window is evaluated with the baseline model.

## Objective

The initial objective is the mean cross-sectional Spearman information coefficient between the
score and forward excess return. It evaluates ranking information rather than optimizing one lucky
portfolio path.

## Search space and regularization

The default search is deterministic and local. Weight mass is shifted in small increments between
components. Candidates must remain non-negative, sum to one, stay within a maximum change per
component and within a total L1 distance from the baseline. Training objective also penalizes drift
from the baseline.

## Promotion gate

A candidate is not automatically promoted because it wins one fold. Promotion requires enough
valid folds, positive mean out-of-sample improvement, a minimum fraction of positive folds and
candidate-selection consensus. Otherwise the baseline remains the production hypothesis.

## Empirical boundary

M16's validation/calibration mechanism is complete, but implementation completion is deliberately
separate from empirical weight promotion. A real promotion requires a sufficiently complete,
point-in-time dataset accepted by the M15/Post-M20 readiness contracts and repeated out-of-sample
evidence satisfying the promotion gate.

If external public sources cannot reconstruct the required historical evidence without revision or
look-ahead ambiguity, no replacement weights are promoted. The versioned baseline remains the
research configuration until stronger evidence exists.
