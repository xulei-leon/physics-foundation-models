# Review Report: Sprint M1-01 Grouped Simulation-Weight Audit

Reviewed artifact: `project/3-Plan/sprint-m1-01.md`

Governing context:

- `project/1-Requirement/FR-001-reference-demo-diagnostics.md`
- `project/3-Plan/2026-07-30-reference-demo-diagnostics-plan.md`
- `docs/software/requirements.md`
- `docs/software/architecture.md`
- `docs/software/specification.md`
- `docs/software/traceability-matrix.md`
- `docs/engineering/data-access-guide.md`
- `docs/engineering/analysis-run-guide.md`
- `docs/engineering/development-and-debugging.md`
- `AGENTS.md` instructions supplied in the review request

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Test | `project/3-Plan/sprint-m1-01.md:90-94`, `project/3-Plan/sprint-m1-01.md:105-115` | The sprint requires `particleml audit data` to emit `simulation_weight_groups`, but the test and verification plan does not require a CLI-level regression or command-path assertion. An implementation could satisfy the dataset helper tests while breaking the user-facing JSON command surface. | The sprint acceptance says `particleml audit data` emits deterministic `simulation_weight_groups` at `sprint-m1-01.md:98`, and the FR requires the groups in the JSON printed by `particleml audit data` at `FR-001-reference-demo-diagnostics.md:70-71`. The verification command only runs `tests/test_ingestion.py` at `sprint-m1-01.md:110`; the traceability matrix maps `CLI-001` to `test_cli.py` at `docs/software/traceability-matrix.md:25`. | Add a focused CLI test in `tests/test_cli.py`, or explicitly extend the sprint verification to run the narrow CLI test that invokes `_audit_data` or `particleml audit data` and asserts the JSON contains deterministic `simulation_weight_groups`. |
| Medium | Test | `project/3-Plan/sprint-m1-01.md:105-115` | The sprint omits contract validation from its verification gates even though it claims existing software and Demo-summary contracts remain unchanged. | The sprint acceptance includes unchanged Demo-summary and scientific contracts at `sprint-m1-01.md:102`, and says verification commands are narrowed from the source adaptation plan at `sprint-m1-01.md:52-53`. The FR minimum verification includes repository contract checks at `FR-001-reference-demo-diagnostics.md:193-195`; the source plan includes `particleml contracts validate` at `2026-07-30-reference-demo-diagnostics-plan.md:272-274`; the analysis guide lists `particleml contracts validate` as offline verification at `docs/engineering/analysis-run-guide.md:13-27`; the CLI specification includes `particleml contracts validate` at `docs/software/specification.md:76-95`. | Add `particleml contracts validate` to the M1-01 verification list. If the sprint intentionally excludes it because M1-01 has no schema changes, state that rationale explicitly and keep it assigned to M1-03. |
| Low | Test | `project/3-Plan/sprint-m1-01.md:76-80`, `project/3-Plan/sprint-m1-01.md:90-94` | The fixture requirements do not explicitly require more than one `process_group`, even though `process_group` is a required grouping key. This leaves one dimension of the grouped-key contract weakly tested. | The sprint implementation task groups by `dataset_id`, `process_group`, `sample_role`, and `split` at `sprint-m1-01.md:79-80`. The fixture requirements require multiple datasets and splits plus a generator variation and data row at `sprint-m1-01.md:76-77`, but do not require distinct `process_group` values. The FR requires grouping by `process_group` at `FR-001-reference-demo-diagnostics.md:59-61`. | Require the focused fixture to include at least two process groups, for example signal and background, and assert that otherwise-identical groups remain separate by `process_group`. |
| Low | Clarity | `project/3-Plan/sprint-m1-01.md:119-126` | The sprint says to record focused verification results but does not identify where that evidence should be recorded before the sprint is marked complete. This can make completion evidence inconsistent across workers. | The implementation sequence says "Run focused verification and record results" at `sprint-m1-01.md:125`, then "Mark M1-01 complete" at `sprint-m1-01.md:126`. The project emphasizes traceable scientific claims and evidence records in the supplied AGENTS.md context, and formal outputs rely on completion records in `docs/software/architecture.md:64-69`. | Specify the expected evidence location, such as a completion note in the sprint document when moved to `project/3-Plan/Done`, a review/workflow record under `docs/4-Reviews`, or an implementation PR/test log. |

## Checks Performed

- Compared M1-01 scope against the grouped simulation-weight requirements in FR-001 and D1 of the source adaptation plan.
- Checked consistency with the documented data/simulation separation, signed `w_yield`, non-negative `w_train`, CLI command surface, and audit-data workflow.
- Checked that the sprint avoids out-of-scope weighted-KS, study-result schema, Demo regression, reference-project imports, new dependencies, and observed-data access.
- Checked verification coverage against the FR minimum verification, source-plan gates, software specification, traceability matrix, and engineering guides.

## Overall Assessment

No Critical or High findings were identified. The sprint is broadly aligned with the governing FR and preserves the main scientific-policy boundaries: data exclusion, signed yield weights, unchanged training weights, no reference-project dependency, no Demo-summary change, and no observed-data access. The actionable gaps are mostly verification precision: the CLI output contract and contract-validation gate should be made explicit, and the focused fixture should cover every grouping key.
