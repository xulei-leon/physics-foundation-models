"""Validate the active particleML v2 documentation and contract suite."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ARCHIVE = DOCS / "archive" / "cms-jet-foundation-v0.4.md"

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
STALE_TERMS = ("CMS", "JetClass", "OmniLearned", "top-tagging")
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
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path == ARCHIVE or relative.startswith(UPSTREAM_ARS):
            continue
        if any(part in {".git", ".venv", "node_modules", "dist"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for term in STALE_TERMS:
            if term.lower() in text.lower():
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


def main() -> int:
    checks = (
        validate_required_files,
        validate_versions_and_status,
        validate_schemas,
        validate_links,
        validate_stale_terms,
        validate_archive,
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
