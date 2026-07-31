# Sprint M1-03 Post-Failure Code Review

## Scope

Reviewed the post-failure fix in `tests/test_demo.py` by static inspection only. I did not run pytest, `tests/test_demo.py`, the Demo, or the complete suite.

The review focused on whether the new `primary_comparison` assertion contract matches the published schema and offline Demo guide, whether it avoids masking unrelated Demo failures, whether the focused non-Demo selection is consistent with the reported `2 passed, 5 deselected`, and whether a second complete pytest run is justified after the diagnosed focused fix.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Info | Contract / Test Review | `tests/test_demo.py:22-29`, `tests/test_demo.py:32-52`, `tests/test_demo.py:100-117`, `schemas/demo-summary.schema.json:137-155`, `docs/engineering/offline-demo-guide.md:83-87` | No actionable finding. The fix matches the schema and documented Demo behavior for a blocked study with unavailable primary expected fit, while preserving the finite-object branch for successful primary comparisons. | The helper permits `primary_comparison is None` only when `study_status == "blocked"` and `blocking_reasons` contains `primary_fit_unavailable`. The schema explicitly allows `primary_comparison` to be either `null` or the required finite comparison object, and the offline guide states an unavailable primary expected fit can set `study_status: blocked` while the outer Demo still publishes completed. The full Demo test validates `demo-summary.json` against the schema before calling the helper, so malformed object shape, missing required fields, extra fields, and unrelated summary contract regressions remain caught by `validate_document`. | Proceed with the fix. Keep the schema validation before the helper in the full Demo test; it is what prevents the helper from becoming a broad substitute for the schema contract. |

## Masking Assessment

The helper is scoped to the failed assertion: it only replaces the prior unconditional `dict` assertion for `summary["primary_comparison"]`. It does not swallow exceptions, alter Demo execution, modify pyhf behavior, or skip existing checks.

Unrelated Demo failures remain visible because `test_full_offline_demo_is_blinded_non_formal_and_freeze_ineligible` still asserts CLI success, reads the published summary, validates the summary schema, checks blinding and synthetic-data invariants, checks all model entries, checks CPU/hist runtime, validates output hashes and exact artifact set, and verifies freeze refusal. If the Demo fails before publication, publishes an invalid summary, changes artifacts, performs network access, or violates blinding/freeze behavior, this test still fails independently of the new helper.

## Focused Selection

The reported focused result, `2 passed, 5 deselected`, is consistent with selecting only `test_demo_primary_comparison_contract` from `tests/test_demo.py`. That test has two parameterized cases and does not call `cli.main`, `run_offline_demo`, or `run_blinded_study`.

The expensive Demo remains in `test_full_offline_demo_is_blinded_non_formal_and_freeze_ineligible`, a separate test function. Under a focused `-k primary_comparison_contract` style selection, that full Demo test is one of the deselected items, so the focused command does not execute the expensive Demo.

## Complete-Suite Rerun

A second complete pytest run is justified by the Sprint failure-handling rule. The first complete run is retained as evidence of the diagnosed failure. `project/3-Plan/sprint-m1-03.md:95-100` requires that after a fix is reviewed and focused tests pass, the M1-03 complete-suite command restarts from the beginning; `project/3-Plan/sprint-m1-03.md:156-157` likewise states that a failed long run is rerun only after a diagnosed and focused fix.

The current state satisfies that prerequisite from a review standpoint: the failure was diagnosed as a schema/documentation-valid `primary_comparison: null` blocked-study outcome, the focused non-Demo test covers both null and finite branches, and this static review found no masking or contract issue.

## Conclusion

No actionable findings were identified. The post-failure test fix is aligned with the schema and offline Demo guide, does not mask unrelated Demo failures, and is eligible for the required restarted complete pytest run after the focused non-Demo verification evidence.
