# Sprint M1-01 Document Review Confirm

**Reviewed Inputs**

- `project/3-Plan/sprint-m1-01.md`
- `project/1-Requirement/FR-001-reference-demo-diagnostics.md`
- `docs/4-Reviews/sprint-m1-01-review-by-gpt-5.5.md`

**Review Date**

- 2026-07-31

## Overall Conclusion

The review is sound and identifies four bounded improvements to the Sprint's
test and evidence plan. None changes the scientific scope. M1-01 can proceed
after the accepted actions below are applied to the Sprint document.

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Test | `gpt-5.5 finding 1` | The user-facing `particleml audit data` JSON path lacks an explicit CLI regression test. | Accept | FR-001 requires `simulation_weight_groups` in the printed audit JSON, while `docs/software/traceability-matrix.md` assigns `CLI-001` evidence to `tests/test_cli.py`; the current `_audit_data` handler is the integration boundary. | Add `tests/test_cli.py` to the Sprint scope, require a focused command-path JSON assertion, and include that test file in focused pytest verification. |
| 2 | Medium | Test | `gpt-5.5 finding 2` | Contract validation is absent although the Sprint claims unchanged contracts. | Accept | FR-001 and the source adaptation plan include repository contract validation, and `particleml contracts validate` already validates the schema suite and strict configurations without running the Demo. | Add `particleml contracts validate` to M1-01 verification. |
| 3 | Low | Test | `gpt-5.5 finding 3` | The fixture does not explicitly cover multiple `process_group` values. | Accept | `process_group` is one of the four required grouping keys in FR-001 and the Sprint; testing only multiple datasets and splits would not isolate that key's behavior. | Require at least two process groups and assert that they remain separate. |
| 4 | Low | Clarity | `gpt-5.5 finding 4` | The Sprint does not say where verification evidence is recorded. | Accept | The Sprint workflow requires verification results in workflow state, and this repository keeps active workflow evidence in Sprint and review-confirm documents rather than a separate state file. | Record commands, results, environment, and remaining risks in the Sprint delivery conclusion and the code-review-confirm document before completion. |

## Needs Immediate Action

- Add the CLI-level audit JSON regression to scope and verification.
- Add contract validation to the verification commands.
- Strengthen the fixture across `process_group`.
- Define the completion-evidence locations.

## Can Be Deferred

- None of the four findings should be deferred because each is a small
  document-level correction within M1-01.

## Final Status

M1-01 is accepted for implementation after all four document actions are
applied. No FR change or repeated document review is required because these
actions only make existing acceptance and verification obligations explicit.
