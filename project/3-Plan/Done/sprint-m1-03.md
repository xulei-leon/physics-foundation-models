# Sprint M1-03 Full Offline Regression and Verification

> **For agentic workers:** Execute this Sprint without subagents and only after
> M1-01 and M1-02 are complete. Treat the complete pytest invocation as one
> long-running standalone task.

**Goal:** Prove the diagnostics across the full offline four-model, five-seed
Demo and complete repository gates without executing the expensive study twice.

**Architecture:** Reuse the existing full Demo integration test and capture its
internal `study_result`. This Sprint is a validation boundary, not a new
production-code feature.

**Tech stack:** Python 3.10-3.12, pytest, CPU/hist offline Demo, repository
contract and VitePress tooling; verified Jetson container for supported formal
environment checks.

**Status:** Complete - full offline regression and repository gates passed.

**Estimated effort:** 1-2 active hours plus the elapsed time of one complete
pytest run and environment-specific Jetson checks.

## 1. Sprint objective

Complete the integration and regression portion of
[FR-001 Non-blocking Analysis Diagnostics](../../1-Requirement/Done/FR-001-reference-demo-diagnostics.md).

Core objectives:

- Assert diagnostics for all four models, five seeds, and ensembles.
- Preserve Demo network isolation and artifact contracts.
- Run the complete pytest suite once as the long-running test task.
- Finish lint, type, contract, documentation, and whitespace verification.

## 2. Prerequisites

- Completed [Sprint M1-01](sprint-m1-01.md).
- Completed [Sprint M1-02](sprint-m1-02.md).
- Focused M1-01 and M1-02 verification results recorded.
- Existing full offline Demo integration test and portable CPU/hist config.

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
- `VERIFICATION_COMMANDS` are the complete repository gates defined by the
  source adaptation plan.

## 3. Included scope

- `tests/test_demo.py`: capture the existing Demo run's internal
  `study_result`.
- Full four-model, seeds 17, 42, 314, 2026, and 2718, and ensemble assertions.
- One complete pytest execution including the offline Demo.
- Ruff, mypy, schema, documentation, Node, VitePress, and diff checks.
- Recording host/Jetson environment boundaries and actual results.

## 4. Out of scope

- New production analysis logic.
- A second Demo or `run_blinded_study` execution for the same verification.
- New plots, Demo artifacts, Demo-summary fields, or observed-data paths.
- Automatic fixes that expand M1-03 into M1-01 or M1-02 implementation scope.
- A formal physics result or replacement for verified CUDA/hist evidence.

## 5. Work scope

### 5.1 Long-running full regression

Implementation and validation tasks:

- [x] Wrap or capture the existing full Demo test's internal `study_result`.
- [x] Assert the diagnostic object for every fixed model's five seeds and
  ensemble.
- [x] Assert finite values or allowed class-specific `null`.
- [x] Assert the Demo remains no-network CPU/hist.
- [x] Assert the published artifact list and strict Demo-summary schema are
  unchanged.
- [x] Confirm no observed-data or real signal-window entry point exists.
- [x] Run the complete pytest suite once; do not first run
  `tests/test_demo.py` separately.
- [x] Run the remaining repository gates after pytest completes.
- [x] Record elapsed time, environment, and results.

Failure handling:

- [x] If the full run exposes an M1-01 or M1-02 production defect, stop M1-03
  and reopen the responsible Sprint rather than silently expanding this scope.
- [x] After a fix is reviewed and focused tests pass, restart the M1-03
  complete-suite command from the beginning.

## 6. Acceptance criteria

- All four models have five seed records plus one ensemble diagnostic record.
- The full offline Demo executes once during the normal verification path.
- The Demo remains deterministic, network-isolated, CPU/hist, blinded, and
  ineligible for freeze.
- Diagnostic values cannot change status, blocking reasons, gates, expected
  significance, the primary comparison, or freeze eligibility.
- All supported repository gates pass.
- Formal CUDA/hist claims remain bound to the verified Jetson environment.

## 7. Verification requirements

Run the long test command once:

```bash
python -m pytest -q
```

After it completes, run:

```bash
python -m ruff check src/particleml scripts tests
python -m mypy src/particleml
particleml contracts validate
python scripts/validate_software_docs.py
node --test
pnpm docs:build
git diff --check
```

Execution rules:

- Do not run `python -m pytest -q tests/test_demo.py` before the complete suite.
- The offline suite validates the portable CPU/hist Demo only.
- Use the verified Jetson container for formal CUDA/hist environment checks.
- Do not install an unsupported Windows host stack to imitate Jetson.

## 8. Implementation sequence

1. Confirm M1-01 and M1-02 completion records.
2. Update `tests/test_demo.py` to capture the existing single Demo study result.
3. Review the assertions without executing the expensive test.
4. Run the complete pytest suite once and retain its result.
5. Run the remaining non-model repository gates.
6. Record environment boundaries and verification evidence.
7. Mark M1-03 and FR-001 complete only when all required evidence exists.

## 9. Risk control

- Avoid duplicate Demo execution by using only the complete-suite pytest command.
- Do not patch production code inside the validation Sprint without reopening
  the responsible implementation Sprint.
- Preserve the Demo artifact list and strict schema with explicit assertions.
- A failed long run is retained as evidence; rerun only after a diagnosed and
  focused fix.
- Existing immutable formal artifacts and observed-data authorization remain
  untouched.

## 10. Delivery conclusion

Complete on 2026-07-31 in the Windows Python 3.12 project `.venv`, after M1-01
commit `2783b10` and M1-02 commit `7d463dc`. The user-requested single
`gpt-5.5` document/code reviews and confirmations are retained under
`docs/4-Reviews/`.

Long-run evidence:

- First `.\.venv\Scripts\python.exe -m pytest -q`: retained failure,
  `109 passed, 1 failed` in 201.45 seconds. The existing Demo assertion required
  a comparison object even though a valid blocked pyhf study published
  `primary_comparison: null`, `study_status: blocked`, and
  `primary_fit_unavailable` as permitted by the strict schema and Demo guide.
- Focused non-Demo regression after the diagnosed assertion fix:
  `.\.venv\Scripts\python.exe -m pytest -q tests/test_demo.py -k "demo_primary_comparison_contract"`:
  passed, 2 tests with 5 deselected. The fix received a separate static review
  and confirmation.
- Required complete-suite restart: passed, 112 tests with 263 warnings in
  246.74 seconds. The rerun executed the offline four-model Demo once and no
  standalone `tests/test_demo.py` or second study command was used.

Remaining repository gates:

- `.\.venv\Scripts\python.exe -m ruff check src/particleml scripts tests`:
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

The portable Demo remained deterministic, network-isolated, CPU/hist, blinded,
and freeze-ineligible with its strict artifact list unchanged. No real observed
data or signal-window entry point ran. This Windows verification does not make
a formal CUDA/hist claim; that evidence remains bound to the documented,
verified Jetson container.
