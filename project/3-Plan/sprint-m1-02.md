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

**Status:** Planned - starts after M1-01 completes.

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

- `FR_DIR=project/1-Requirement` and `SPRINT_DIR=project/3-Plan` are explicitly
  selected by the user.
- No review directory or persistent workflow-state file is requested.
- Verification commands are derived from the source adaptation plan and
  narrowed to evaluation, study, schema, and documentation changes.

## 3. Included scope

- `src/particleml/evaluation.py`: weighted KS and aligned diagnostic helpers.
- `src/particleml/study.py`: seed and ensemble run-record integration.
- `schemas/study-result.schema.json`: optional diagnostic object.
- `tests/test_evaluation.py`: primitive, contract, and non-blocking tests.
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

- [ ] Add failing tests for identical, disjoint, negative-weight, malformed,
  non-finite, misaligned, empty-positive-weight, and shifted-shape cases.
- [ ] Implement `weighted_ks_distance` for aligned one-dimensional arrays.
- [ ] Use absolute weights, stable sorting, and right-continuous empirical CDFs.
- [ ] Raise `ContractError` for malformed or non-finite inputs.
- [ ] Add a minimal aligned-array helper for nominal simulation `target`,
  `raw_score`, `split`, and `w_yield`.
- [ ] Exclude data and generator variations.
- [ ] Return `null` for one class only when train or test lacks positive
  absolute weight.
- [ ] Attach `raw_score_shape_diagnostics` to every seed and ensemble run for
  cut-based, Logistic Regression, XGBoost, and MLP.
- [ ] Compute the record before DDT interpretation.
- [ ] Extend only the optional study-result property and retain contract version
  `2.1.0`.
- [ ] Update the four scoped documentation files.

Test requirements:

- [ ] Identical distributions return zero and disjoint distributions return one.
- [ ] Negative weights contribute through their absolute values.
- [ ] Invalid inputs fail closed with `ContractError`.
- [ ] Diagnostic-only value changes cannot affect status, `blocking_reasons`,
  gate sets, expected significance, the primary comparison, or freeze
  eligibility.
- [ ] Run-record fields contain no threshold, pass/fail, or blocking semantics.

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
python -m pytest -q tests/test_evaluation.py
python -m ruff check src/particleml/evaluation.py src/particleml/study.py tests/test_evaluation.py
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
7. Mark M1-02 complete before starting M1-03.

## 9. Risk control

- Never use a signed cumulative sum as a probability distribution.
- Keep the record free of thresholds and gate semantics.
- Test non-blocking behavior directly rather than relying on documentation.
- If schema integration requires a broader contract change, stop and revise
  the FR before implementation.
- Roll back helper, run-record, schema, tests, and documentation together.

## 10. Delivery conclusion

Pending M1-01 completion, implementation, and focused verification.
