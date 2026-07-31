# Sprint M1-03 Code Review by GPT-5.5

Review date: 2026-07-31

Review type: code review

Scope:

- Primary implementation target: `tests/test_demo.py`
- Governing Sprint: `project/3-Plan/sprint-m1-03.md`
- Confirmation record: `docs/4-Reviews/sprint-m1-03-review-confirm.md`
- Evidence inspected: current working-tree diff, `src/particleml/demo.py`,
  `src/particleml/study.py`, `schemas/demo-summary.schema.json`, and
  `schemas/study-result.schema.json`

Tests were not run. Per review instructions, this review used static inspection
only and did not execute `tests/test_demo.py`, the Demo, or the complete suite.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Low | Maintainability / Typing | `tests/test_demo.py:35-50` | The capture wrapper erases the exact `run_blinded_study` tuple contract and stores deeply indexed study data as `dict[str, object]`. This does not create a second Demo execution or a runtime failure in the current test, but it weakens the assertion-only guard and would not be type-sound if test type checking is expanded. | `capture_study` is annotated as returning `tuple[dict[str, object], ...]` with `*args: object, **kwargs: object`, while `src/particleml/study.py:220-229` returns exactly `tuple[dict[str, Any], dict[str, Any], dict[str, Any]]`. The test then indexes nested members from `captured_study_result["models"][name]["runs"]` at `tests/test_demo.py:91-108`, even though the local annotation says the first index returns `object`. | Preserve the exact return shape in the wrapper, for example by annotating it as `tuple[dict[str, Any], dict[str, Any], dict[str, Any]]` and importing `Any`, or by casting the captured result components to `Mapping[str, Any]` after asserting the tuple shape. |

## Coverage Assessment

The wrapper captures the existing Demo call rather than launching a second study.
`src/particleml/demo.py:500-509` calls the module-global
`run_blinded_study`, and `tests/test_demo.py:42-54` saves that original callable,
monkeypatches `particleml.demo.run_blinded_study`, delegates to the original, and
asserts `study_call_count == 1` at `tests/test_demo.py:88`.

The diagnostic assertions cover all expected model and run dimensions. The test
compares captured study models to `MODEL_ROLES` at `tests/test_demo.py:91`; the
model constants define the four required models at `src/particleml/models.py:24-35`.
It builds labels from `FORMAL_SEEDS` plus `ensemble` at `tests/test_demo.py:92`
and requires each model's runs to match that set at `tests/test_demo.py:93-95`.

The finite-or-null diagnostic contract is covered for both KS values at
`tests/test_demo.py:96-108`, matching the strict diagnostic schema in
`schemas/study-result.schema.json`. The assertions also verify that diagnostics
do not appear in captured gate sets or blocking reasons at
`tests/test_demo.py:109-115`.

Existing and new assertions preserve the Demo's no-network, CPU/hist, blinded,
non-formal, and output/schema contracts: network clients are forbidden at
`tests/test_demo.py:52-53`; runtime CPU/hist is asserted at
`tests/test_demo.py:85-86`; blinding and no signal-window data are asserted at
`tests/test_demo.py:68-73`; formal CUDA/hist remains checked from the formal
config at `tests/test_demo.py:117-119`; `demo-summary` validation and strict
published output assertions are at `tests/test_demo.py:65-67` and
`tests/test_demo.py:124-139`. These align with the strict output and runtime
properties in `schemas/demo-summary.schema.json`.

## Conclusion

No Critical, High, or Medium issues were found. The assertion-only change set
meets the M1-03 intent of observing the single existing offline Demo study run
and checking diagnostics across four models, five seeds, and ensembles without
adding production behavior or invoking a second Demo execution.
