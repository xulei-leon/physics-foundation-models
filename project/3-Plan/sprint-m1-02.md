# Sprint M1-02 Weighted Raw-Score Diagnostics

> **For agentic workers:** Execute this Sprint without subagents and only after
> M1-01 is complete. Do not start the long-running M1-03 validation until this
> Sprint is complete.

**Goal:** Implement class-conditional train-versus-test raw-score weighted KS
diagnostics in every fixed-model study run without adding a scientific gate.

**Architecture:** Extend the existing evaluation and blinded-study paths with
small NumPy helpers and one optional study-result field. Reuse aligned
predictions and existing run records.

**Tech stack:** Python 3.10-3.12, NumPy, pytest, Draft 2020-12 JSON Schema.

**Status:** Complete - implementation, reviews, and focused verification passed.

**Estimated effort:** 3-4 active hours.

## 1. Sprint objective

Implement the weighted raw-score portion of
[FR-001 Non-blocking Analysis Diagnostics](../1-Requirement/FR-001-reference-demo-diagnostics.md).

Core objectives:

- Provide a correct absolute-weighted two-sample KS primitive.
- Attach descriptive signal/background diagnostics to seed and ensemble runs.
- Preserve study status, expected fits, gates, freeze eligibility, and the
  primary comparison.

## 2. Prerequisites

- Completed [Sprint M1-01](sprint-m1-01.md).
- [Reference Demo Diagnostics Adaptation Plan](2026-07-30-reference-demo-diagnostics-plan.md),
  section D2.
- Existing aligned raw predictions, fixed model roles, study orchestration, and
  study-result schema.

Workflow resolution:

- `FR_DIR=project/1-Requirement`,
  `FR_BACKLOG_DIR=project/1-Requirement/backlog`, and
  `FR_DONE_DIR=project/1-Requirement/Done` are resolved from the repository
  layout.
- `DESIGN_DIR=docs/software` is the active architecture and software-contract
  source; `SPRINT_DIR=project/3-Plan` and
  `SPRINT_DONE_DIR=project/3-Plan/Done` are resolved from the repository
  layout.
- `REVIEW_DIR=docs/4-Reviews` and `REVIEW_DONE_DIR=docs/4-Reviews/Done` reuse
  the review directory established by M1-01.
- `WORKFLOW_STATE_PATH` is unset because no persistent workflow-state file was
  requested.
- `VERIFICATION_COMMANDS` are derived from the source adaptation plan and
  narrowed to evaluation, study, schema, and documentation changes.

## 3. Included scope

- `src/particleml/evaluation.py`: weighted KS and aligned diagnostic helpers.
- `src/particleml/study.py`: seed and ensemble run-record integration.
- `schemas/study-result.schema.json`: optional diagnostic object.
- `tests/test_evaluation.py`: primitive, contract, and non-blocking tests.
- `tests/test_study.py`: lightweight seed/ensemble run-record integration.
- `tests/test_contracts.py`: positive and negative nested-schema validation.
- `docs/research/model-selection.md`: diagnostic role.
- `docs/software/specification.md`: input and output contract.
- `docs/engineering/analysis-run-guide.md`: interpretation.
- `docs/engineering/development-and-debugging.md`: malformed-input behavior.

## 4. Out of scope

- The grouped weight audit delivered by M1-01.
- Long-running full Demo and complete repository regression, deferred to M1-03.
- A KS threshold, `passed` field, gate, blocking reason, or automatic retuning.
- DDT, template, expected-fit, freeze, blinding, or Demo-summary changes.
- New dependencies or reference-project code.

## 5. Work scope

### 5.1 Weighted KS and study integration

Implementation tasks:

- [x] Add failing tests for identical, disjoint, negative-weight, malformed,
  non-finite, misaligned, empty-positive-weight, and shifted-shape cases.
- [x] Implement `weighted_ks_distance` for aligned one-dimensional arrays.
- [x] Use absolute weights, stable sorting, and right-continuous empirical CDFs.
- [x] Raise `ContractError` for malformed or non-finite inputs.
- [x] Make `weighted_ks_distance` reject either sample when its total absolute
  weight is not positive.
- [x] Add a prediction-frame adapter that explicitly filters
  `is_data == false` and `sample_role == "nominal"`, then extracts aligned
  `target`, `raw_score`, `split`, and `w_yield` arrays.
- [x] Exclude data and generator variations before computing either class.
- [x] Return `null` only for the affected class when its train or test sample
  lacks positive absolute weight; still compute the other class when valid.
- [x] Attach `raw_score_shape_diagnostics` to every seed and ensemble run for
  cut-based, Logistic Regression, XGBoost, and MLP.
- [x] Compute the record before DDT interpretation.
- [x] Extend only the nested optional study-result property and retain contract
  version `2.1.0`; validate constants, nullable `[0,1]` values, and reject extra
  diagnostic fields.
- [x] Update the four scoped documentation files.

Test requirements:

- [x] Identical distributions return zero and disjoint distributions return one.
- [x] Negative weights contribute through their absolute values.
- [x] A tied-score asymmetric-weight case proves right-continuous CDF semantics
  and rejects accidental DDT-midrank reuse.
- [x] Invalid inputs fail closed with `ContractError`.
- [x] Data and generator-variation rows with extreme raw scores cannot affect
  either class diagnostic.
- [x] Positive and negative schema tests cover malformed values and forbidden
  extra fields inside `raw_score_shape_diagnostics`.
- [x] A lightweight study integration test covers all four model keys and
  `seed-17`, `seed-42`, `seed-314`, `seed-2026`, `seed-2718`, plus `ensemble`
  without running the full Demo.
- [x] Diagnostic-only value changes cannot affect status, `blocking_reasons`,
  gate sets, expected significance, the primary comparison, or freeze
  eligibility.
- [x] Run-record fields contain no threshold, pass/fail, or blocking semantics.

## 6. Acceptance criteria

- The primitive returns a finite distance in `[0,1]` for valid weighted samples.
- Signal and background diagnostics use nominal simulation train/test
  `raw_score` values only.
- Seed and ensemble run records accept the optional schema field.
- Scientific and blinding behavior is unchanged.
- Documentation consistently describes the record as non-blocking.
- Focused verification passes without running the full Demo.

## 7. Verification requirements

Run:

```bash
python -m pytest -q tests/test_evaluation.py tests/test_study.py tests/test_contracts.py
python -m ruff check src/particleml/evaluation.py src/particleml/study.py tests/test_evaluation.py tests/test_study.py tests/test_contracts.py
python -m mypy src/particleml
particleml contracts validate
python scripts/validate_software_docs.py
node --test
pnpm docs:build
git diff --check
```

Do not run `tests/test_demo.py` or the complete pytest suite in this Sprint.

## 8. Implementation sequence

1. Add weighted-KS primitive and failure tests.
2. Implement the minimal evaluation helpers.
3. Add study run-record integration and schema validation.
4. Add non-blocking regression assertions.
5. Update interpretation and debugging documentation.
6. Run focused verification and record results.
7. Record commands, results, environment, and remaining risks in this Sprint's
   delivery conclusion and code-review-confirm document.
8. Mark M1-02 complete before starting M1-03.

## 9. Risk control

- Never use a signed cumulative sum as a probability distribution.
- Keep the record free of thresholds and gate semantics.
- Test non-blocking behavior directly rather than relying on documentation.
- If schema integration requires a broader contract change, stop and revise
  the FR before implementation.
- Roll back helper, run-record, schema, tests, and documentation together.

## 10. Delivery conclusion

Complete on 2026-07-31 in the Windows Python 3.12 project `.venv`, after the
M1-01 prerequisite commit `2783b10`. The user-requested single `gpt-5.5`
document and code reviews, plus both point-by-point confirmations, are retained
under `docs/4-Reviews/`.

Verification evidence:

- `.\.venv\Scripts\python.exe -m pytest -q tests/test_evaluation.py tests/test_study.py tests/test_contracts.py`:
  passed, 38 tests.
- `.\.venv\Scripts\python.exe -m ruff check src/particleml/evaluation.py src/particleml/study.py tests/test_evaluation.py tests/test_study.py tests/test_contracts.py`:
  passed.
- `.\.venv\Scripts\python.exe -m mypy src/particleml`: passed, 23 source
  files checked.
- `.\.venv\Scripts\particleml.exe contracts validate`: passed, 12 contract
  schemas/configurations validated.
- `.\.venv\Scripts\python.exe scripts/validate_software_docs.py`: passed,
  7 checks.
- `node --test`: passed, 3 tests.
- `pnpm docs:build`: passed.
- `git diff --check`: passed.

No M1-02 blocker remains. The full Demo and complete pytest suite were not run
and remain assigned to M1-03. These portable host checks make no formal Jetson
CUDA validation claim.
