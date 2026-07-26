"""Direct-HTTPS dataset catalog policy and checksum-verified downloads."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import zlib
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from .contracts import (
    ContractError,
    canonical_json_bytes,
    sha256_document,
    sha256_file,
    validate_document,
)

PROCESS_GROUPS = frozenset(
    {"data", "signal", "irreducible_background", "reducible_background"}
)
SAMPLE_ROLES = frozenset({"nominal", "generator_variation"})
MC_FILE_PATTERN = re.compile(r"_mc_(?P<dataset_number>\d+)\.")


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
    require_https(str(catalog["metadata_table"]["url"]))
    for record in catalog["records"]:
        require_https(str(record["metadata_url"]))
    seen_urls: set[str] = set()
    seen_dataset_numbers: set[int] = set()
    seen_signal_partitions: set[tuple[str, str]] = set()
    for item in catalog["files"]:
        url = str(item["url"])
        require_https(url)
        if url in seen_urls:
            raise ContractError("CATALOG_DUPLICATE_URL", f"duplicate file URL: {url}")
        seen_urls.add(url)
        group = str(item["process_group"])
        if group not in PROCESS_GROUPS:
            raise ContractError("CATALOG_PROCESS", f"unsupported process group: {group}")
        role = str(item["sample_role"])
        if role not in SAMPLE_ROLES:
            raise ContractError("CATALOG_SAMPLE_ROLE", f"unsupported sample role: {role}")
        if bool(item["is_data"]):
            if role != "nominal":
                raise ContractError("CATALOG_DATA_ROLE", "data files must be nominal")
            continue
        dataset_number = int(item["dataset_number"])
        if dataset_number in seen_dataset_numbers:
            raise ContractError(
                "CATALOG_DUPLICATE_DATASET",
                f"dataset number appears more than once: {dataset_number}",
            )
        seen_dataset_numbers.add(dataset_number)
        if role == "generator_variation":
            if group != "signal" or item.get("variation_of") is None:
                raise ContractError(
                    "CATALOG_VARIATION",
                    "generator variations must be signal and identify variation_of",
                )
        if group == "signal" and bool(item.get("is_nominal", False)):
            generator_group = str(item.get("generator_group", ""))
            partition = str(item.get("partition", "inclusive"))
            key = (generator_group, partition)
            if key in seen_signal_partitions:
                raise ContractError(
                    "CATALOG_DUPLICATE_SIGNAL",
                    f"multiple nominal signal samples for {generator_group}/{partition}",
                )
            seen_signal_partitions.add(key)


def make_catalog(
    catalog_id: str,
    records: Iterable[Mapping[str, Any]],
    files: Iterable[Mapping[str, Any]],
    metadata_table: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a frozen catalog from explicitly resolved entries."""

    catalog = {
        "schema_version": "2.1.0",
        "catalog_id": catalog_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "metadata_table": dict(
            metadata_table
            or {
                "url": "https://example.invalid/metadata.csv",
                "sha256": "0" * 64,
            }
        ),
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


def fetch_bytes_https(
    url: str,
    *,
    accept: str = "application/octet-stream",
    timeout_seconds: float = 60.0,
) -> bytes:
    """Fetch bytes with an explicit HTTPS GET and verified redirect policy."""

    require_https(url)
    with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
        response = client.get(url, headers={"Accept": accept})
        response.raise_for_status()
        require_https(str(response.url))
        return bytes(response.content)


def _normalize_adler32(value: str) -> str:
    prefix, separator, digest = value.lower().partition(":")
    if separator != ":" or prefix != "adler32" or not re.fullmatch(r"[0-9a-f]{8}", digest):
        raise ContractError("CATALOG_ADLER32", f"invalid official checksum: {value}")
    return digest


def cache_https_file(
    url: str,
    cache: Path,
    cache_name: str,
    *,
    expected_size: int,
    expected_adler32: str,
    timeout_seconds: float = 300.0,
) -> tuple[Path, str]:
    """Cache one HTTPS file after size, Adler-32, and SHA-256 verification."""

    require_https(url)
    if Path(cache_name).name != cache_name or not cache_name:
        raise ContractError("CATALOG_CACHE_NAME", f"unsafe cache name: {cache_name}")
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / cache_name
    partial = cache / f"{cache_name}.partial"
    expected_adler = _normalize_adler32(expected_adler32)

    def verify(path: Path) -> str:
        size = 0
        adler = 1
        sha256 = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                adler = zlib.adler32(chunk, adler)
                sha256.update(chunk)
        actual_adler = f"{adler & 0xFFFFFFFF:08x}"
        if size != expected_size:
            raise ContractError(
                "CATALOG_SIZE",
                f"{url} expected {expected_size} bytes, found {size}",
            )
        if actual_adler != expected_adler:
            raise ContractError(
                "CATALOG_ADLER32",
                f"{url} expected {expected_adler}, found {actual_adler}",
            )
        return sha256.hexdigest()

    if destination.exists():
        return destination, verify(destination)
    if partial.exists():
        partial.unlink()
    try:
        size = 0
        adler = 1
        sha256 = hashlib.sha256()
        with httpx.stream("GET", url, follow_redirects=True, timeout=timeout_seconds) as response:
            response.raise_for_status()
            require_https(str(response.url))
            with partial.open("xb") as stream:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    adler = zlib.adler32(chunk, adler)
                    sha256.update(chunk)
                    stream.write(chunk)
        actual_adler = f"{adler & 0xFFFFFFFF:08x}"
        if size != expected_size:
            raise ContractError(
                "CATALOG_SIZE",
                f"{url} expected {expected_size} bytes, downloaded {size}",
            )
        if actual_adler != expected_adler:
            raise ContractError(
                "CATALOG_ADLER32",
                f"{url} expected {expected_adler}, downloaded {actual_adler}",
            )
        os.replace(partial, destination)
        return destination, sha256.hexdigest()
    finally:
        if partial.exists():
            partial.unlink()


def _metadata_rows(payload: bytes) -> dict[int, dict[str, str]]:
    try:
        text = payload.decode("utf-8-sig")
        reader = csv.DictReader(text.splitlines())
        rows = {
            int(row["dataset_number"]): dict(row)
            for row in reader
            if row.get("dataset_number")
        }
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ContractError("CATALOG_METADATA_TABLE", "invalid metadata CSV") from exc
    if not rows:
        raise ContractError("CATALOG_METADATA_TABLE", "metadata CSV is empty")
    return rows


def _configured_samples(config: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    samples = cast(Mapping[str, Any], config["samples"])
    output: dict[int, dict[str, Any]] = {}

    def add(dataset_number: int, record: Mapping[str, Any]) -> None:
        if dataset_number in output:
            raise ContractError(
                "CATALOG_SAMPLE_DUPLICATE",
                f"duplicate configured dataset number: {dataset_number}",
            )
        output[dataset_number] = dict(record)

    for item in cast(Iterable[Mapping[str, Any]], samples["nominal_signal"]):
        dataset_number = int(item["dataset_number"])
        add(
            dataset_number,
            {
                "process_group": "signal",
                "sample_role": "nominal",
                "production_mode": str(item["production_mode"]),
                "partition": str(item["partition"]),
                "variation_of": None,
            },
        )
    for item in cast(Iterable[Mapping[str, Any]], samples["generator_variations"]):
        dataset_number = int(item["dataset_number"])
        add(
            dataset_number,
            {
                "process_group": "signal",
                "sample_role": "generator_variation",
                "production_mode": str(item["production_mode"]),
                "partition": str(item["partition"]),
                "variation_of": int(item["replaces"]),
            },
        )
    for value in cast(Iterable[object], samples["irreducible_background"]):
        dataset_number = int(str(value))
        add(
            dataset_number,
            {
                "process_group": "irreducible_background",
                "sample_role": "nominal",
                "production_mode": None,
                "partition": "inclusive",
                "variation_of": None,
            },
        )
    reducible = cast(Mapping[str, Any], samples["reducible_background"])
    for family in ("zjets", "ttbar"):
        for value in cast(Iterable[object], reducible[family]):
            dataset_number = int(str(value))
            add(
                dataset_number,
                {
                    "process_group": "reducible_background",
                    "sample_role": "nominal",
                    "production_mode": None,
                    "partition": family,
                    "variation_of": None,
                },
            )
    variation_targets = {
        int(record["variation_of"])
        for record in output.values()
        if record["sample_role"] == "generator_variation"
    }
    missing_targets = sorted(variation_targets - set(output))
    if missing_targets:
        raise ContractError(
            "CATALOG_VARIATION_TARGET",
            f"variation targets are not nominal samples: {missing_targets}",
        )
    return output


def freeze_catalog(config: Mapping[str, Any], cache: Path) -> dict[str, Any]:
    """Resolve and freeze the configured ATLAS sample allowlist."""

    records_config = cast(Iterable[Mapping[str, Any]], config["records"])
    record_documents: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    for configured in records_config:
        record_id = str(configured["record_id"])
        metadata_url = str(configured["metadata_url"])
        document = fetch_json_https(metadata_url)
        record_documents[record_id] = document
        records.append(
            {
                "record_id": record_id,
                "kind": str(configured["kind"]),
                "metadata_url": metadata_url,
                "metadata_sha256": sha256_document(document),
            }
        )

    metadata_url = str(config["metadata_table_url"])
    metadata_payload = fetch_bytes_https(metadata_url, accept="text/csv")
    metadata_rows = _metadata_rows(metadata_payload)
    configured_samples = _configured_samples(config)
    base_url = str(config["download_base_url"])
    require_https(base_url)

    files: list[dict[str, Any]] = []
    for record_id, document in record_documents.items():
        metadata = cast(Mapping[str, Any], document.get("metadata"))
        record_files = cast(Iterable[Mapping[str, Any]], metadata.get("files"))
        is_data = record_id == "atlas-93924"
        for source in record_files:
            key = str(source["key"])
            match = MC_FILE_PATTERN.search(key)
            dataset_number = (
                None
                if is_data
                else int(match.group("dataset_number"))
                if match
                else None
            )
            if not is_data and dataset_number not in configured_samples:
                continue
            if not is_data and dataset_number is None:
                raise ContractError("CATALOG_FILE_NAME", f"cannot parse dataset number: {key}")
            url = f"{base_url.rstrip('/')}/{key}"
            expected_size = int(source["size"])
            official_checksum = str(source["checksum"])
            _, sha256 = cache_https_file(
                url,
                cache,
                key,
                expected_size=expected_size,
                expected_adler32=official_checksum,
            )
            if is_data:
                policy = {
                    "process_group": "data",
                    "sample_role": "nominal",
                    "production_mode": None,
                    "partition": key,
                    "variation_of": None,
                }
                normalization: dict[str, Any] = {}
            else:
                assert dataset_number is not None
                policy = configured_samples[dataset_number]
                if dataset_number not in metadata_rows:
                    raise ContractError(
                        "CATALOG_METADATA_MISSING",
                        f"metadata CSV has no row for {dataset_number}",
                    )
                row = metadata_rows[dataset_number]
                normalization = {
                    "xsec_pb": float(row["crossSection_pb"]),
                    "kfactor": float(row["kFactor"]),
                    "filter_efficiency": float(row["genFiltEff"]),
                    "sum_of_generator_weights": float(row["sumOfWeights"]),
                }
            files.append(
                {
                    "dataset_id": f"data-{key}" if is_data else f"mc-{dataset_number}",
                    "dataset_number": dataset_number,
                    "record_id": record_id,
                    "url": url,
                    "cache_name": key,
                    "sha256": sha256,
                    "adler32": _normalize_adler32(official_checksum),
                    "size_bytes": expected_size,
                    "is_data": is_data,
                    "process_group": policy["process_group"],
                    "sample_role": policy["sample_role"],
                    "production_mode": policy["production_mode"],
                    "partition": policy["partition"],
                    "variation_of": policy["variation_of"],
                    "generator_group": policy["production_mode"],
                    "is_nominal": policy["sample_role"] == "nominal",
                    **normalization,
                }
            )

    found_mc = {
        int(item["dataset_number"])
        for item in files
        if not bool(item["is_data"])
    }
    missing = sorted(set(configured_samples) - found_mc)
    if missing:
        raise ContractError("CATALOG_SAMPLE_MISSING", f"record is missing DSIDs: {missing}")
    catalog = make_catalog(
        str(config["catalog_id"]),
        records,
        files,
        {
            "url": metadata_url,
            "sha256": hashlib.sha256(metadata_payload).hexdigest(),
        },
    )
    return catalog


def publish_catalog(path: Path, catalog: Mapping[str, Any]) -> Path:
    """Publish a validated catalog atomically without overwriting evidence."""

    validate_catalog(catalog)
    if path.exists():
        raise ContractError("CATALOG_DESTINATION", f"catalog already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.partial")
    if partial.exists():
        partial.unlink()
    try:
        partial.write_bytes(canonical_json_bytes(dict(catalog)))
        json.loads(partial.read_text(encoding="utf-8"))
        os.replace(partial, path)
        return path
    finally:
        if partial.exists():
            partial.unlink()


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
