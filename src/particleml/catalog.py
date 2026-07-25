"""Direct-HTTPS dataset catalog policy and checksum-verified downloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .contracts import ContractError, sha256_file, validate_document

PROCESS_GROUPS = frozenset(
    {"data", "signal", "irreducible_background", "reducible_background"}
)


def require_https(url: str) -> None:
    """Reject every network scheme except direct HTTPS."""

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ContractError("CATALOG_HTTPS", f"only direct HTTPS URLs are allowed: {url}")
    if parsed.username or parsed.password:
        raise ContractError("CATALOG_CREDENTIALS", "catalog URLs must not embed credentials")


def classify_process(sample_name: str, is_data: bool) -> str:
    """Classify a declared public sample name or fail closed."""

    if is_data:
        return "data"
    lowered = sample_name.lower()
    if "h125" in lowered and ("zz4l" in lowered or "zz4lep" in lowered):
        return "signal"
    if "zz" in lowered:
        return "irreducible_background"
    if any(token in lowered for token in ("zjets", "z+jets", "ttbar", "tbar", "top")):
        return "reducible_background"
    raise ContractError("CATALOG_UNKNOWN_PROCESS", f"unclassified simulated sample: {sample_name}")


def validate_catalog(catalog: Mapping[str, Any]) -> None:
    """Validate schema and direct-HTTPS/process invariants."""

    validate_document(catalog, "dataset-catalog")
    for record in catalog["records"]:
        require_https(str(record["metadata_url"]))
    seen_urls: set[str] = set()
    nominal_signal_groups: dict[str, str] = {}
    for item in catalog["files"]:
        url = str(item["url"])
        require_https(url)
        if url in seen_urls:
            raise ContractError("CATALOG_DUPLICATE_URL", f"duplicate file URL: {url}")
        seen_urls.add(url)
        group = str(item["process_group"])
        if group not in PROCESS_GROUPS:
            raise ContractError("CATALOG_PROCESS", f"unsupported process group: {group}")
        if group == "signal" and bool(item.get("is_nominal", False)):
            generator_group = str(item.get("generator_group", ""))
            dataset_id = str(item["dataset_id"])
            existing_dataset = nominal_signal_groups.get(generator_group)
            if existing_dataset is not None and existing_dataset != dataset_id:
                raise ContractError(
                    "CATALOG_DUPLICATE_SIGNAL",
                    f"multiple nominal signal samples for {generator_group}",
                )
            nominal_signal_groups[generator_group] = dataset_id


def make_catalog(
    catalog_id: str,
    records: Iterable[Mapping[str, Any]],
    files: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate a frozen catalog from explicitly resolved entries."""

    catalog = {
        "schema_version": "2.0.0",
        "catalog_id": catalog_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "records": [dict(record) for record in records],
        "files": [dict(item) for item in files],
    }
    validate_catalog(catalog)
    return catalog


def fetch_json_https(url: str, timeout_seconds: float = 30.0) -> dict[str, Any]:
    """Fetch one JSON object through a direct verified HTTPS request."""

    require_https(url)
    with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
        response = client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        require_https(str(response.url))
        value = response.json()
    if not isinstance(value, dict):
        raise ContractError("CATALOG_METADATA", f"{url} did not return a JSON object")
    return value


def download_https(
    url: str,
    destination: Path,
    expected_sha256: str,
    timeout_seconds: float = 120.0,
) -> Path:
    """Download to a partial file, verify SHA-256, and publish atomically."""

    require_https(url)
    if destination.exists():
        raise ContractError("CATALOG_DESTINATION", f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.partial")
    if partial.exists():
        partial.unlink()
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=timeout_seconds) as response:
            response.raise_for_status()
            require_https(str(response.url))
            with partial.open("wb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
        actual = sha256_file(partial)
        if actual != expected_sha256:
            raise ContractError(
                "CATALOG_CHECKSUM",
                f"{url} expected {expected_sha256}, downloaded {actual}",
            )
        partial.rename(destination)
        return destination
    finally:
        if partial.exists():
            partial.unlink()
