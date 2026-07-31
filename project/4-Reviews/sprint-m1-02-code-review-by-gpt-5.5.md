# Sprint M1-02 Code Review by GPT-5.5

**Review date:** 2026-07-31

**Scope reviewed**

- Working-tree diff for the requested implementation targets.
- Untracked `tests/test_study.py` integration test.
- Governing Sprint plan `project/3-Plan/sprint-m1-02.md`.
- Review confirmation `docs/4-Reviews/sprint-m1-02-review-confirm.md`.

**Verification note**

I did not run the full Demo or the complete pytest suite. I used focused code inspection through the repository graph and small local behavior probes for the adapter edge cases cited below.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Contract | `src/particleml/evaluation.py:86`, `src/particleml/evaluation.py:87`, `tests/test_evaluation.py:64` | The study-level raw-score diagnostic adapter leaks pandas/NumPy conversion errors instead of failing through `ContractError` for non-numeric `raw_score` or `w_yield`. | `_class_shape_distance` calls `selected["raw_score"].to_numpy(dtype=np.float64)` and `selected["w_yield"].to_numpy(dtype=np.float64)` outside a `try` block. The primitive tests cover malformed arrays only through `weighted_ks_distance`, but there is no adapter-level malformed-frame test. A probe with a nominal train row containing `raw_score="bad"` raised `ValueError: could not convert string to float: 'bad'`; the same happened for `w_yield="bad"`. This contradicts the Sprint/debugging contract that malformed diagnostic inputs fail closed with `ContractError`. | Wrap the adapter conversions and re-raise `ContractError("KS_TYPE", ...)`, or pass the raw split arrays directly into `weighted_ks_distance` so the primitive owns numeric conversion. Add `raw_score_shape_diagnostics` tests for non-numeric score and weight columns. |
| Medium | Correctness | `src/particleml/evaluation.py:108`, `src/particleml/evaluation.py:111`, `src/particleml/evaluation.py:114` | Invalid non-integral nominal targets can be silently truncated into valid class labels, changing class-specific KS/null semantics instead of rejecting the frame. | The adapter checks missing targets, then casts `nominal["target"] = nominal["target"].astype(int)` before validating membership in `{0, 1}`. Pandas truncates values such as `0.5` to `0`, so a malformed target can be reassigned to background. A probe with one nominal signal train row set to `target=0.5` returned a diagnostic with `signal_weighted_ks: null` and `background_weighted_ks: 0.5` instead of raising `ContractError`. | Validate targets before integer casting, or convert numerically and require every finite value to be exactly `0` or `1` before assigning integer labels. Add an adapter test for fractional and otherwise non-binary simulation targets. |
| Low | Typing | `src/particleml/evaluation.py:103`, `src/particleml/evaluation.py:104` | `is_data` filtering is not equivalent to the documented `is_data == false` boundary for object/string payloads, so malformed typing can silently remove all nominal simulation rows and produce null diagnostics. | The adapter uses `~frame["is_data"].astype(bool)`. In pandas, non-empty strings such as `"False"` cast to `True`; a probe with all four nominal simulation rows using `is_data="False"` returned both class distances as `null` rather than computing the expected train/test KS values or raising a contract error. | Require `is_data` to be boolean/`np.bool_`, or explicitly normalize only accepted boolean representations before filtering. Reject unsupported values with `ContractError("KS_TYPE", ...)` and add a test that prevents silent string-bool exclusion. |

## Checked Areas Without Actionable Findings

- `weighted_ks_distance` uses absolute weights, rejects zero-total primitive samples, evaluates right-continuous CDFs at observed scores, and handles tied-score semantics correctly.
- `raw_score_shape_diagnostics` excludes data rows and `sample_role != "nominal"` rows for well-typed prediction frames.
- `run_blinded_study` attaches the diagnostic before DDT transformation and includes it in each seed and ensemble run summary.
- The study-result schema constrains the optional nested diagnostic object without changing schema version `2.1.0`.
