"""Validate the active particleML v2 documentation and contract suite."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ARCHIVE_CANDIDATES = tuple((DOCS / "archive").glob("*v0.4.md"))
ARCHIVE = ARCHIVE_CANDIDATES[0] if len(ARCHIVE_CANDIDATES) == 1 else DOCS / "archive" / "missing.md"

REQUIRED_FILES = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "configs" / "analysis-v1.yaml",
    ROOT / "configs" / "catalog-sources.yaml",
    DOCS / "index.md",
    DOCS / "plans" / "2026-07-25-atlas-h4l-v1-migration-plan.md",
    ARCHIVE,
    DOCS / "research" / "research-plan.md",
    DOCS / "research" / "dataset-and-backgrounds.md",
    DOCS / "research" / "model-selection.md",
    DOCS / "research" / "statistical-analysis-plan.md",
    DOCS / "software" / "requirements.md",
    DOCS / "software" / "architecture.md",
    DOCS / "software" / "specification.md",
    DOCS / "software" / "traceability-matrix.md",
    DOCS / "engineering" / "development-and-debugging.md",
    DOCS / "engineering" / "data-access-guide.md",
    DOCS / "engineering" / "analysis-run-guide.md",
    DOCS / "references" / "h4l-literature-dossier.md",
)
SCHEMAS = (
    "dataset-catalog",
    "dataset-manifest",
    "split-manifest",
    "run-record",
    "prediction-metadata",
    "analysis-freeze",
    "fit-result",
)
STALE_TERMS = ("C" + "MS", "Jet" + "Class", "Omni" + "Learned", "top-" + "tagging")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".mjs"}
UPSTREAM_ARS = ".agents/skills/academic-research-suite/ars/"
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def fail(message: str) -> None:
    raise AssertionError(message)


def validate_required_files() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_FILES if not path.is_file()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")


def validate_versions_and_status() -> None:
    research = (DOCS / "research" / "research-plan.md").read_text(encoding="utf-8")
    requirements = (DOCS / "software" / "requirements.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    index = (DOCS / "index.md").read_text(encoding="utf-8")
    for token, source in (
        ("Research Plan v1.0.0", research),
        ("Software Requirements 2.0.0", requirements),
        ('version = "0.2.0"', pyproject),
        ("blinded", index.lower()),
        ("planned", requirements),
    ):
        if token not in source:
            fail(f"required version/status token is absent: {token}")
    if "observed fit | planned" not in requirements:
        fail("the observed fit must remain planned")


def validate_schemas() -> None:
    for name in SCHEMAS:
        path = ROOT / "schemas" / f"{name}.schema.json"
        if not path.is_file():
            fail(f"missing schema: {path.relative_to(ROOT)}")
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"{path.name} does not declare Draft 2020-12")
        if "/2.0.0/" not in str(schema.get("$id", "")):
            fail(f"{path.name} does not use contract version 2.0.0")


def validate_links() -> None:
    failures: list[str] = []
    for source in DOCS.rglob("*.md"):
        text = source.read_text(encoding="utf-8")
        for target in LINK_PATTERN.findall(text):
            clean = target.split("#", 1)[0]
            if not clean or clean.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (source.parent / clean).resolve()
            if not resolved.exists():
                failures.append(f"{source.relative_to(ROOT)} -> {target}")
    if failures:
        fail("broken documentation links: " + "; ".join(failures))


def validate_stale_terms() -> None:
    failures: list[str] = []
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    for relative in result.stdout.splitlines():
        path = ROOT / relative
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path == ARCHIVE or relative.startswith(UPSTREAM_ARS):
            continue
        if any(part in {".git", ".venv", "node_modules", "dist"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for term in STALE_TERMS:
            pattern = rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"{relative}: {term}")
    if failures:
        fail("active stale terminology found: " + "; ".join(failures))


def validate_archive() -> None:
    text = ARCHIVE.read_text(encoding="utf-8")
    required = (
        "facaa72c3ad095c2f8aaca7e8dbba6ae164a774c",
        "e2b546c6016249b58a92d1cbb9fc639a48559bff",
        "157 passed, 1 skipped",
        "archived, not completed",
        "not pushed remotely",
    )
    for token in required:
        if token not in text:
            fail(f"legacy index is missing: {token}")


def validate_local_archive_refs() -> None:
    """Verify local archive refs when they are present in this checkout."""

    text = ARCHIVE.read_text(encoding="utf-8")
    tag_match = re.search(r"\*\*Annotated tag:\*\* `([^`]+)`", text)
    branch_match = re.search(r"\*\*Archive branch:\*\* `([^`]+)`", text)
    if tag_match is None or branch_match is None:
        fail("legacy index does not declare its tag and branch")
    tag = tag_match.group(1)
    branch = branch_match.group(1)
    tag_exists = (
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"], cwd=ROOT
        ).returncode
        == 0
    )
    branch_exists = (
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=ROOT
        ).returncode
        == 0
    )
    if not tag_exists and not branch_exists:
        return
    if not tag_exists or not branch_exists:
        fail("only one local archive ref exists")
    tag_commit = subprocess.check_output(
        ["git", "rev-list", "-n", "1", tag], cwd=ROOT, text=True
    ).strip()
    branch_commit = subprocess.check_output(
        ["git", "rev-parse", branch], cwd=ROOT, text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "show", "-s", "--format=%T", tag_commit], cwd=ROOT, text=True
    ).strip()
    if tag_commit != "facaa72c3ad095c2f8aaca7e8dbba6ae164a774c":
        fail("local archive tag commit does not match the recorded commit")
    if branch_commit != tag_commit:
        fail("local archive branch and tag do not resolve to the same commit")
    if tree != "e2b546c6016249b58a92d1cbb9fc639a48559bff":
        fail("local archive tree does not match the pre-migration tree")


def main() -> int:
    checks = (
        validate_required_files,
        validate_versions_and_status,
        validate_schemas,
        validate_links,
        validate_stale_terms,
        validate_archive,
        validate_local_archive_refs,
    )
    try:
        for check in checks:
            check()
    except (AssertionError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"documentation validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"documentation validation passed ({len(checks)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
