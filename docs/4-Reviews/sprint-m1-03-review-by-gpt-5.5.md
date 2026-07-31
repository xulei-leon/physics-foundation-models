# Sprint M1-03 Document Review by GPT-5.5

Review type: document review

Reviewed file: `project/3-Plan/sprint-m1-03.md`

Governing context:

- `project/1-Requirement/FR-001-reference-demo-diagnostics.md`
- `project/3-Plan/2026-07-30-reference-demo-diagnostics-plan.md`
- Completed M1-01 and M1-02 sprint documents and commits `2783b10` and `7d463dc`
- `tests/test_demo.py`
- `src/particleml/demo.py`
- `src/particleml/study.py`
- `schemas/demo-summary.schema.json`
- `schemas/study-result.schema.json`
- `docs/engineering/offline-demo-guide.md`
- Repository verification gate list in the source adaptation plan

No tests or Demo execution were run for this document review.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Info | Requirement | `project/3-Plan/sprint-m1-03.md` | No actionable document findings were identified. The Sprint is aligned with FR-001 and is specific enough to govern the M1-03 validation work without requiring a second expensive Demo run. | The plan requires capturing the existing Demo test's internal `study_result` (`sprint-m1-03.md:10-11`, `61-62`, `82`, `143`), forbids a second Demo or `run_blinded_study` execution (`71`, `90-91`, `135`), asserts all four models, five seeds, and ensembles (`63`, `83`, `103`), preserves artifact and strict Demo-summary contracts (`31`, `72`, `87-88`, `155`), retains no-network CPU/hist and blinding checks (`86`, `106`, `136-138`), mandates one complete pytest command plus repository gates (`90-93`, `119-132`), and defines failure/reopen behavior (`95-99`, `153-156`). This matches FR-001's offline regression requirements (`FR-001-reference-demo-diagnostics.md:121-124`, `185-195`) and the source adaptation plan's D3/verification boundary. The current code path also supports a single-run capture approach: `run_offline_demo` receives `study_result` from `run_blinded_study` (`src/particleml/demo.py:500-511`) while publishing only the fixed summary and artifact set (`512-552`), and `run_blinded_study` records `raw_score_shape_diagnostics` before DDT for each seed and ensemble run (`src/particleml/study.py:267-283`). | Proceed with M1-03 as written. During implementation, keep the capture test-local or otherwise non-contractual so `run_offline_demo`'s published artifact list, return contract, and `demo-summary.json` schema remain unchanged. |

## Review Notes

- M1-01 is marked complete with focused verification evidence, and commit `2783b10` contains the grouped simulation-weight audit implementation, tests, documentation, and review records.
- M1-02 is marked complete with focused verification evidence, and commit `7d463dc` contains weighted KS diagnostics, study integration, schema coverage, documentation, and review records.
- The existing full Demo test already checks HTTP isolation via `httpx` monkeypatching, fixed model roles, fixed seeds, CPU/hist runtime, formal CUDA/hist configuration immutability, strict Demo-summary validation, published output hashes, forbidden formal artifacts, and freeze ineligibility.
- The Demo summary schema keeps `additionalProperties: false`, fixes runtime `xgboost_device` to `cpu`, fixes `tree_method` to `hist`, and enumerates the fixed output artifact keys, so M1-03's unchanged-contract assertions have concrete schema support.
- The study-result schema accepts the optional `raw_score_shape_diagnostics` object with fixed `comparison`, fixed `weighting`, nullable KS values in `[0, 1]`, and no additional diagnostic fields.
- The Sprint correctly separates portable Windows/CPU-hist regression evidence from formal CUDA/hist claims, which remain tied to the verified Jetson environment.

## Conclusion

`project/3-Plan/sprint-m1-03.md` is ready for execution. I found no Critical, High, Medium, or Low document issues.
