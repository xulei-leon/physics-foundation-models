# Sprint M1-02 Document Review Confirm

**Reviewed Inputs**

- `project/3-Plan/sprint-m1-02.md`
- `project/1-Requirement/FR-001-reference-demo-diagnostics.md`
- `docs/4-Reviews/sprint-m1-02-review-by-gpt-5.5.md`

**Review Date**

- 2026-07-31

## Overall Conclusion

All six findings are supported by repository evidence. They clarify existing
FR-001 obligations without expanding the scientific feature: the filtering
boundary, lightweight study integration evidence, nested schema validation,
tie semantics, class-specific null handling, and current prerequisite state.
M1-02 can proceed after these actions are applied to the Sprint document.

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Correctness | `gpt-5.5 finding 1` | Four numeric arrays cannot themselves prove data and generator variations were excluded. | Accept | The prediction payload retains `is_data` and `sample_role`, and `run_blinded_study` currently passes complete raw prediction frames into DDT. FR-001 explicitly excludes data and generator variations. | Add a prediction-frame adapter that filters `is_data == false` and `sample_role == "nominal"` before extracting aligned arrays, and test extreme excluded rows. |
| 2 | High | Test | `gpt-5.5 finding 2` | M1-02 lacks executable focused evidence that every model seed and ensemble run receives the record. | Accept | `run_blinded_study` constructs six labels per model inside one loop, while the full Demo is intentionally deferred. A lightweight study unit can exercise the run-summary attachment boundary without running the Demo. | Add `tests/test_study.py` with a lightweight synthetic or monkeypatched integration assertion covering four model keys and all five seed labels plus ensemble; retain full Demo coverage for M1-03. |
| 3 | High | Contract | `gpt-5.5 finding 3` | The current schema does not inspect nested run records, so merely adding an unconstrained property would not validate the diagnostic. | Accept | `models.additionalProperties` currently accepts any object. FR-001 requires validation of the optional diagnostic while preserving version `2.1.0`. | Add a narrowly scoped nested run schema for the optional diagnostic constants, nullable `[0,1]` values, and `additionalProperties: false`; add positive and negative contract tests, including forbidden extra diagnostic fields. |
| 4 | Medium | Test | `gpt-5.5 finding 4` | Existing planned cases do not distinguish right-continuous tied-score CDFs from midranks. | Accept | The DDT implementation uses midranks, while the source plan explicitly requires a different right-continuous KS convention. | Add a repeated-score, asymmetric-weight test with an exact expected distance that would fail under midranks or interpolation. |
| 5 | Medium | Correctness | `gpt-5.5 finding 5` | Zero-total primitive failure and class-specific helper null behavior are ambiguous. | Accept | FR-001 distinguishes malformed/invalid primitive inputs, which fail closed, from an absent positive class/split weight, which yields `null` only for that class. | Require `weighted_ks_distance` to raise `ContractError` for either zero-total sample; require the higher-level helper to return `null` only for the affected class while computing the other. |
| 6 | Low | Consistency | `gpt-5.5 finding 6` | M1-02 still describes M1-01 as pending. | Accept | M1-01 is complete and committed as `2783b10`. | Mark the prerequisite satisfied and the M1-02 document confirmed for implementation. |

## Needs Immediate Action

- Apply all six bounded Sprint-document corrections before implementation.

## Can Be Deferred

- The expensive full Demo assertion remains correctly assigned to M1-03.

## Final Status

M1-02 is accepted for implementation after all six document actions are
applied. No FR revision or repeated document review is required.
