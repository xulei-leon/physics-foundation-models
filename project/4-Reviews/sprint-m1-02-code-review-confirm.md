# Sprint M1-02 Code Review Confirm

**Reviewed Inputs**

- `src/particleml/evaluation.py`
- `src/particleml/study.py`
- `schemas/study-result.schema.json`
- `tests/test_evaluation.py`
- `tests/test_study.py`
- `tests/test_contracts.py`
- `docs/4-Reviews/sprint-m1-02-code-review-by-gpt-5.5.md`

**Review Date**

- 2026-07-31

## Overall Conclusion

The review found three real adapter-boundary defects. All are accepted because
malformed prediction-frame values must fail through `ContractError`, not be
silently filtered, truncated, or exposed as raw pandas/NumPy exceptions. The
weighted-KS primitive, study attachment, and schema design need no broader
change.

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Contract | `gpt-5.5 finding 1` | Non-numeric adapter score or weight values leak `ValueError`. | Accept | `_class_shape_distance` converts pandas columns to `float64` outside the primitive's guarded numeric conversion. The documented malformed-input contract requires `ContractError`. | Add failing adapter tests for non-numeric score and weight values, then wrap conversions and raise `KS_TYPE`. |
| 2 | Medium | Correctness | `gpt-5.5 finding 2` | Fractional targets are truncated by `astype(int)` and reassigned to a class. | Accept | Pandas integer conversion maps `0.5` to `0` before the current binary-membership check. This changes class-specific null and KS values. | Validate finite numeric targets as exactly `0` or `1` before integer conversion and add fractional/non-binary tests. |
| 3 | Low | Correctness | `gpt-5.5 finding 3` | String `is_data` values are truthy and can silently exclude simulation rows. | Accept | `astype(bool)` treats non-empty strings, including `"False"`, as true. The adapter's filtering contract requires an actual boolean boundary. | Require every `is_data` value to be `bool`/`np.bool_`, reject other representations with `KS_TYPE`, and add a regression test. |

## Needs Immediate Action

- Apply all three fixes and rerun the complete M1-02 focused verification.

## Can Be Deferred

- No accepted code-review action should be deferred.

## Final Status

The implementation is accepted. All three adapter fixes passed their focused
regressions, and final M1-02 verification passed on 2026-07-31 in the Windows
Python 3.12 project `.venv`: 38 focused tests, Ruff, mypy over 23 source files,
12 contract validations, 7 documentation checks, 3 Node tests, VitePress
build, and `git diff --check`. No review action or blocker remains.
