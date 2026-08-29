# M16 — Walk-Forward Calibration

Status: **implemented in v1.6 candidate**.

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

## Important limitation

M16 implements the validation/calibration mechanism; it does not claim that v1.4 weights have
already been empirically optimized. A real promotion requires a sufficiently complete historical,
point-in-time dataset produced by M1-M15.
