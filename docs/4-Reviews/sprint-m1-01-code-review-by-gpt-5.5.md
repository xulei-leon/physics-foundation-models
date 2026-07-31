# Sprint M1-01 Code Review by GPT-5.5

**Review Type:** Code review

**Reviewed Change Set**

- `src/particleml/dataset.py`
- `src/particleml/cli.py`
- `tests/test_ingestion.py`
- `tests/test_cli.py`
- `docs/engineering/data-access-guide.md`

**Governing Inputs**

- `project/3-Plan/sprint-m1-01.md`
- `docs/4-Reviews/sprint-m1-01-review-confirm.md`

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Info | Review | `src/particleml/dataset.py:31`, `src/particleml/cli.py:157`, `tests/test_ingestion.py:127`, `tests/test_cli.py:21`, `docs/engineering/data-access-guide.md:58` | No actionable findings were identified in the reviewed M1-01 diff. | The helper groups simulation rows by `dataset_id`, `process_group`, `sample_role`, and `split`, excludes data rows, preserves signed and absolute sums separately, checks finite grouped values, and copies the selected slice before grouping. The CLI adds the result to the existing `particleml audit data` JSON after `audit_frame` succeeds. Tests cover deterministic ordering, data exclusion, nominal versus generator-variation separation, process-group separation, input immutability, non-finite `w_yield`, retained `audit_frame` failures, and the CLI JSON path. Documentation states that the fields are diagnostics and not yield-rescaling or `w_train` recomputation inputs. | Proceed with M1-01. Keep the completed verification evidence with the Sprint closeout and do not broaden this change into M1-02 behavior. |

## Checks Performed

- Reviewed the current working-tree diff for the five implementation files.
- Compared the diff against the M1-01 Sprint scope and the accepted review-confirm actions.
- Checked correctness, scientific-policy compliance, deterministic output, finite-number handling, input immutability, data exclusion, CLI behavior, typing, and missing-test risk.
- Used the codebase knowledge graph for repository context checks around audit, weight, and sample-role usage.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest -q tests/test_ingestion.py tests/test_cli.py
```

Result: `9 passed`.

```bash
.\.venv\Scripts\python.exe -m ruff check src/particleml/dataset.py src/particleml/cli.py tests/test_ingestion.py tests/test_cli.py
```

Result: passed.

```bash
.\.venv\Scripts\python.exe -m mypy src/particleml
```

Result: passed.

```bash
.\.venv\Scripts\python.exe -m particleml.cli contracts validate
```

Result: passed.

```bash
.\.venv\Scripts\python.exe scripts/validate_software_docs.py
```

Result: passed.

```bash
git diff --check -- src/particleml/dataset.py src/particleml/cli.py tests/test_ingestion.py tests/test_cli.py docs/engineering/data-access-guide.md
```

Result: passed.
