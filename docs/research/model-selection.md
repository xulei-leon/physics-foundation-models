# Model Selection

## Decision

XGBoost is the primary classifier because the selected inputs form a compact
tabular feature set, event counts are limited, nonlinear interactions are
expected, and tree ensembles offer strong performance without a
deep-learning-framework dependency.

## Comparators

| Model | Role | Main value | Main limitation |
|---|---|---|---|
| Cut-based | physics baseline | transparent and independent of training | limited nonlinear discrimination |
| Logistic Regression | linear ML baseline | tests value of nonlinear structure | cannot capture complex interactions |
| XGBoost | primary model | robust tabular nonlinear classifier | can sculpt mass through correlated inputs |
| sklearn MLP | neural control | tests whether a small dense network changes the conclusion | more scale- and initialization-sensitive |

All learned models use the same split, feature contract, training weights,
seeds, and evaluation events. Raw scores are used only for classification
metrics. The statistical fit consumes DDT categories.

## Frozen tuning

Only validation events and seed 42 may inform hyperparameter choices. The
parameters in `configs/analysis-v1.yaml` are then frozen for all five formal
seeds. Test results must not trigger additional tuning.

The formal XGBoost backend uses the validated Jetson CUDA build with the
histogram tree method. The device is part of the hashed configuration; changing
it requires a new reviewed configuration and new artifacts.

## Interpretation

A raw AUC gain is insufficient. The primary model is scientifically usable
only if it improves expected sensitivity after DDT and passes all sculpting
gates. If XGBoost fails a gate, v1 reports that failure; it does not silently
substitute a different model.
