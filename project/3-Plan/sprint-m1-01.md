# Sprint M1-01 Grouped Simulation-Weight Audit

> **For agentic workers:** Execute this Sprint without subagents. Follow
> `AGENTS.md` and do not start M1-02 until this Sprint is complete.

**Goal:** Add deterministic grouped simulation-weight diagnostics to the
existing data-audit command without changing canonical data, training weights,
or Demo-summary contracts.

**Architecture:** Reuse the audited canonical frame and current CLI JSON path.
Add one pure dataset helper; do not create a new audit subsystem.

**Tech stack:** Python 3.10-3.12, pandas, pytest.

**Status:** Ready - document authoring complete; implementation not started.

**Estimated effort:** 2-3 active hours.

## 1. Sprint objective

Implement the grouped simulation-weight portion of
[FR-001 Non-blocking Analysis Diagnostics](../1-Requirement/FR-001-reference-demo-diagnostics.md).

Core objectives:

- Summarize signed and absolute simulation weights deterministically.
- Expose the summaries through `particleml audit data`.
- Prove data exclusion and preserve existing weight contracts.

## 2. Prerequisites

- [Reference Demo Diagnostics Adaptation Plan](2026-07-30-reference-demo-diagnostics-plan.md),
  section D1.
- Existing canonical-frame audit and CLI data-audit implementation.
- Software Requirements 2.1.0: `DATA-004`, `DATA-005`, and `CLI-001`.

Workflow resolution:

- `FR_DIR=project/1-Requirement` and `SPRINT_DIR=project/3-Plan` are explicitly
  selected by the user.
- No review directory or persistent workflow-state file is requested.
- Verification commands are derived from the source adaptation plan and
  narrowed to the files touched by this Sprint.

## 3. Included scope

- `src/particleml/dataset.py`: one pure grouped summary helper.
- `src/particleml/cli.py`: `simulation_weight_groups` in data-audit JSON.
- `tests/test_ingestion.py`: focused grouping and contract coverage.
- `docs/engineering/data-access-guide.md`: field definitions and interpretation.

## 4. Out of scope

- Weighted KS evaluation, study records, and schema changes; these belong to
  M1-02.
- Full Demo and complete repository regression; these belong to M1-03.
- Weight recomputation, rescaling, split changes, or Demo-summary changes.
- Reference-project imports, new dependencies, or observed-data access.

## 5. Work scope

### 5.1 Grouped simulation-weight audit

Implementation tasks:

- [ ] Add a focused failing fixture with positive and negative nominal weights,
  a generator variation, multiple datasets and splits, and a data row.
- [ ] Add one pure helper that consumes an already audited canonical frame.
- [ ] Exclude data and group by `dataset_id`, `process_group`, `sample_role`,
  and `split`.
- [ ] Emit `events`, `negative_events`, `negative_fraction`, `sum_w_yield`,
  and `sum_abs_w_yield` with finite values and deterministic ordering.
- [ ] Preserve signed `w_yield`; use `abs(w_yield)` only for the absolute sum.
- [ ] Keep nominal and generator-variation samples distinguishable.
- [ ] Do not mutate the input or recompute `w_train`.
- [ ] Add the result to `_audit_data` as `simulation_weight_groups`.
- [ ] Keep `audit_frame` unchanged.
- [ ] Document that the fields are diagnostics, not rescaling inputs.

Test requirements:

- [ ] Assert exact counts, signed sums, absolute sums, and negative fractions.
- [ ] Assert deterministic group ordering and complete data exclusion.
- [ ] Retain existing non-finite-weight and data-training-weight failures.

## 6. Acceptance criteria

- `particleml audit data` emits deterministic `simulation_weight_groups`.
- No data row appears in a group.
- Nominal and generator-variation groups remain distinguishable.
- The canonical frame and `w_train` are unchanged.
- Existing Demo-summary and scientific contracts are unchanged.
- Focused verification passes.

## 7. Verification requirements

Run:

```bash
python -m pytest -q tests/test_ingestion.py
python -m ruff check src/particleml/dataset.py src/particleml/cli.py tests/test_ingestion.py
python -m mypy src/particleml
python scripts/validate_software_docs.py
git diff --check
```

Do not run the full Demo or complete pytest suite in this Sprint.

## 8. Implementation sequence

1. Add the focused failing ingestion fixture.
2. Implement the pure summary helper.
3. Expose it through the existing CLI JSON object.
4. Update the data-access guide.
5. Run focused verification and record results.
6. Mark M1-01 complete before starting M1-02.

## 9. Risk control

- Fail on non-finite values rather than publishing misleading summaries.
- Preserve signed and absolute sums as separate fields.
- Keep data exclusion explicit and tested.
- Roll back the helper, CLI field, focused tests, and documentation together;
  no published formal artifact is rewritten.

## 10. Delivery conclusion

Pending implementation and focused verification.
