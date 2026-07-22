#!/usr/bin/env python3
"""Validate one DeepSeek research batch before it is proposed for review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker
from license_expression import get_spdx_licensing


ROOT = Path(__file__).resolve().parents[1]
DOSSIER_SCHEMA = Path("schema/research-dossier-v1.schema.json")
MANIFEST_SCHEMA = Path("schema/research-batch-manifest-v1.schema.json")
TAXONOMY = Path("schema/research-taxonomy-v1.json")
WORKER_CONFIG = Path("data/quarantine/research/worker-config.json")

TAXONOMY_FIELDS = {
    "classification.domain_ids": "domain_ids",
    "classification.subdomain_ids": "subdomain_ids",
    "classification.task_ids": "task_ids",
    "classification.capability_ids": "capability_ids",
    "classification.project_types": "project_types",
    "technology.programming_languages": "programming_languages",
    "technology.frameworks": "frameworks",
    "technology.runtimes": "runtimes",
    "technology.protocols": "protocols",
    "technology.data_types": "data_types",
    "delivery.modes": "delivery_modes",
    "delivery.package_formats": "package_formats",
    "delivery.orchestrators": "orchestrators",
    "platforms.operating_systems": "operating_systems",
    "platforms.execution_targets": "execution_targets",
    "platforms.cpu_architectures": "cpu_architectures",
    "platforms.accelerators": "accelerators",
}

FORBIDDEN_LICENSE_OBLIGATION_KEYS = {
    "attribution",
    "commercial_use",
    "distribution",
    "modification",
    "network_source_disclosure",
    "patent_grant",
    "source_disclosure",
}

VERIFIED_NULL_PATHS = {
    "repository.fork_parent_repository_id",
    "repository.mirror_url",
}

NO_INFERENCE_PATH_PREFIXES = ("licensing.", "releases", "security.")
LICENSE_REF_PATTERN = re.compile(
    r"^(?:DocumentRef-[A-Za-z0-9.-]+:)?LicenseRef-[A-Za-z0-9.-]+$"
)
SPDX_LICENSING = get_spdx_licensing()

SENSITIVE_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]{6,}"),
    re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)[^\s\"']+"),
)

GITHUB_IDENTITY_FIELDS = {
    "node_id": "platform_node_id",
    "full_name": "full_name",
    "default_branch": "default_branch",
    "fork": "is_fork",
    "mirror_url": "mirror_url",
    "archived": "archived",
    "disabled": "disabled",
    "created_at": "created_at",
}

GITHUB_MONOTONIC_TIME_FIELDS = ("updated_at", "pushed_at")

SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
VERSION_COMPARATOR_PATTERN = re.compile(r"^(>=|>|<=|<|=)(.+)$")

EVIDENCE_SOURCE_PATH_PREFIXES = {
    "repository_api": (
        "repository.platform_repository_id",
        "repository.platform_node_id",
        "repository.full_name",
        "repository.canonical_url",
        "repository.default_branch",
        "repository.visibility",
        "repository.is_fork",
        "repository.fork_parent_repository_id",
        "repository.mirror_url",
        "repository.archived",
        "repository.disabled",
        "repository.created_at",
        "repository.updated_at",
        "repository.pushed_at",
        "lifecycle.latest_activity_at",
        "relations",
    ),
    "repository_commit": ("repository.default_branch_oid",),
    "readme": (
        "localized_content.",
        "classification.",
        "technology.",
        "delivery.",
        "platforms.",
        "natural_language_support.",
        "lifecycle.",
        "quality.",
        "relations",
    ),
    "license_file": ("licensing.",),
    "notice_file": ("licensing.",),
    "release": ("releases", "licensing.version_rules", "lifecycle."),
    "documentation": (
        "localized_content.",
        "classification.",
        "technology.",
        "delivery.",
        "platforms.",
        "natural_language_support.",
        "licensing.",
        "releases",
        "lifecycle.",
        "security.",
        "quality.",
        "relations",
    ),
    "security_policy": ("security.",),
    "advisory": ("security.",),
    "maintainer_announcement": (
        "repository.name_history",
        "licensing.",
        "releases",
        "lifecycle.",
        "security.",
        "quality.",
        "relations",
    ),
}

REPOSITORY_BOUND_EVIDENCE_TYPES = {
    "repository_api",
    "repository_commit",
    "readme",
    "license_file",
    "notice_file",
    "release",
    "security_policy",
    "advisory",
}

GITHUB_API_VERSION = "2022-11-28"
MAX_GITHUB_RESPONSE_BYTES = 10 * 1024 * 1024


def _load_json(path: Path, errors: list[str], label: str) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} is missing: {path}")
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
    except OSError as exc:
        errors.append(f"cannot read {label} {path}: {exc}")
    return None


def _format_path(path: Any) -> str:
    return ".".join(str(part) for part in path) or "<root>"


def _schema_errors(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{label} schema error at {_format_path(error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    ]


def _nested_value(payload: dict[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _value_is_explicitly_unknown(value: Any) -> bool:
    return value is None or value == "unknown"


def _value_is_compatible_with_unknown_state(value: Any) -> bool:
    return _value_is_explicitly_unknown(value) or value == []


def _collect_reference_ids(dossier: dict[str, Any]) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    for path, state in dossier.get("field_states", {}).items():
        for evidence_id in state.get("evidence_ids", []):
            references.append((f"field_states.{path}", evidence_id))
    for index, item in enumerate(dossier.get("licensing", {}).get("version_rules", [])):
        for evidence_id in item.get("evidence_ids", []):
            references.append((f"licensing.version_rules[{index}]", evidence_id))
    for index, item in enumerate(dossier.get("releases", [])):
        for evidence_id in item.get("evidence_ids", []):
            references.append((f"releases[{index}]", evidence_id))
    for index, item in enumerate(dossier.get("relations", [])):
        for evidence_id in item.get("evidence_ids", []):
            references.append((f"relations[{index}]", evidence_id))
    for index, item in enumerate(dossier.get("repository", {}).get("name_history", [])):
        for evidence_id in item.get("evidence_ids", []):
            references.append((f"repository.name_history[{index}]", evidence_id))
    return references


def _evidence_parent_path(source: str) -> str:
    normalized = source.removeprefix("field_states.")
    return normalized.split("[", 1)[0]


def _scan_sensitive(payload: Any, label: str) -> list[str]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return [f"{label} contains a sensitive value or private path"] if any(
        pattern.search(rendered) for pattern in SENSITIVE_PATTERNS
    ) else []


def _canonical_repository_url(value: Any) -> Any:
    return value.rstrip("/") if isinstance(value, str) else value


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _path_supported_by_source(path: str, source_type: str) -> bool:
    return any(
        path == prefix or (prefix.endswith(".") and path.startswith(prefix))
        for prefix in EVIDENCE_SOURCE_PATH_PREFIXES.get(source_type, ())
    )


def _evidence_belongs_to_repository(
    evidence_url: Any,
    source_type: Any,
    repository_id: Any,
    full_name: Any,
) -> bool:
    if source_type not in REPOSITORY_BOUND_EVIDENCE_TYPES:
        return True
    if not all(isinstance(value, str) and value for value in (evidence_url, repository_id, full_name)):
        return False
    parsed = urlparse(evidence_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc == "api.github.com":
        if len(parts) >= 2 and parts[0] == "repositories":
            return parts[1] == repository_id
        if len(parts) >= 3 and parts[0] == "repos":
            return "/".join(parts[1:3]).casefold() == full_name.casefold()
        return False
    if parsed.netloc in {"github.com", "raw.githubusercontent.com"} and len(parts) >= 2:
        return "/".join(parts[:2]).casefold() == full_name.casefold()
    return False


def _parse_version(value: str) -> tuple[int, int, int] | None:
    match = SEMVER_PATTERN.fullmatch(value)
    return tuple(map(int, match.groups())) if match else None


def _parse_version_range(
    value: Any,
) -> tuple[tuple[int, int, int] | None, bool, tuple[int, int, int] | None, bool] | None:
    if value == "*":
        return None, False, None, False
    if not isinstance(value, str) or not value:
        return None
    exact = _parse_version(value)
    if exact is not None:
        return exact, True, exact, True

    lower: tuple[int, int, int] | None = None
    lower_inclusive = False
    upper: tuple[int, int, int] | None = None
    upper_inclusive = False
    for token in value.split(" "):
        match = VERSION_COMPARATOR_PATTERN.fullmatch(token)
        if not match:
            return None
        operator, version_text = match.groups()
        version = _parse_version(version_text)
        if version is None:
            return None
        if operator == "=":
            candidate_lower = (version, True)
            candidate_upper = (version, True)
        elif operator in {">", ">="}:
            candidate_lower = (version, operator == ">=")
            candidate_upper = None
        else:
            candidate_lower = None
            candidate_upper = (version, operator == "<=")
        if candidate_lower is not None:
            if lower is None or candidate_lower[0] > lower:
                lower, lower_inclusive = candidate_lower
            elif candidate_lower[0] == lower:
                lower_inclusive = lower_inclusive and candidate_lower[1]
        if candidate_upper is not None:
            if upper is None or candidate_upper[0] < upper:
                upper, upper_inclusive = candidate_upper
            elif candidate_upper[0] == upper:
                upper_inclusive = upper_inclusive and candidate_upper[1]
    if lower is not None and upper is not None:
        if lower > upper or (lower == upper and not (lower_inclusive and upper_inclusive)):
            return None
    return lower, lower_inclusive, upper, upper_inclusive


def _version_ranges_overlap(
    left: tuple[tuple[int, int, int] | None, bool, tuple[int, int, int] | None, bool],
    right: tuple[tuple[int, int, int] | None, bool, tuple[int, int, int] | None, bool],
) -> bool:
    left_lower, left_lower_inclusive, left_upper, left_upper_inclusive = left
    right_lower, right_lower_inclusive, right_upper, right_upper_inclusive = right
    lower, lower_inclusive = left_lower, left_lower_inclusive
    if lower is None or (right_lower is not None and right_lower > lower):
        lower, lower_inclusive = right_lower, right_lower_inclusive
    elif right_lower == lower and lower is not None:
        lower_inclusive = lower_inclusive and right_lower_inclusive
    upper, upper_inclusive = left_upper, left_upper_inclusive
    if upper is None or (right_upper is not None and right_upper < upper):
        upper, upper_inclusive = right_upper, right_upper_inclusive
    elif right_upper == upper and upper is not None:
        upper_inclusive = upper_inclusive and right_upper_inclusive
    if lower is None or upper is None:
        return True
    return lower < upper or (lower == upper and lower_inclusive and upper_inclusive)


def validate_github_enumeration(
    dossiers: list[dict[str, Any]],
    manifest: dict[str, Any],
    github_page: Any,
    *,
    repository_details_by_id: dict[str, dict[str, Any]] | None = None,
    default_branch_oids_by_id: dict[str, str | None] | None = None,
) -> list[str]:
    """Verify a batch queue and repository identities against one GitHub API page."""

    errors: list[str] = []
    input_info = manifest.get("input", {}) if isinstance(manifest, dict) else {}
    queued_ids = input_info.get("repository_ids", [])
    since = input_info.get("since")
    if not isinstance(queued_ids, list):
        return ["manifest input.repository_ids must be an array for GitHub enumeration"]
    if not isinstance(github_page, list):
        return ["GitHub enumeration response must be an array"]
    if len(github_page) < len(queued_ids):
        errors.append(
            "GitHub enumeration response is shorter than the manifest queue"
        )

    page_ids: list[str] = []
    page_by_id: dict[str, dict[str, Any]] = {}
    previous_id: int | None = None
    for index, item in enumerate(github_page, start=1):
        if not isinstance(item, dict):
            errors.append(f"GitHub enumeration item {index} must be an object")
            continue
        repository_id = item.get("id")
        if not isinstance(repository_id, int) or isinstance(repository_id, bool) or repository_id <= 0:
            errors.append(f"GitHub enumeration item {index} has invalid id")
            continue
        if previous_id is not None and repository_id <= previous_id:
            errors.append("GitHub enumeration ids must be strictly increasing")
        previous_id = repository_id
        repository_id_text = str(repository_id)
        page_ids.append(repository_id_text)
        page_by_id[repository_id_text] = item
        if isinstance(since, str) and since.isdigit() and repository_id <= int(since):
            errors.append(
                f"GitHub enumeration id {repository_id_text} is not greater than since={since}"
            )

    expected_ids = page_ids[: len(queued_ids)]
    if queued_ids != expected_ids:
        errors.append(
            "manifest repository_ids do not match the GitHub enumeration sequence"
        )

    for dossier_index, dossier in enumerate(dossiers, start=1):
        repository = dossier.get("repository", {})
        repository_id = repository.get("platform_repository_id")
        api_item = page_by_id.get(repository_id)
        label = f"record {dossier_index}"
        if api_item is None:
            errors.append(
                f"{label} repository id {repository_id!r} is absent from the GitHub enumeration page"
            )
            continue
        if api_item.get("private") is not False:
            errors.append(f"{label} GitHub repository is not public")
        if repository.get("visibility") != "public":
            errors.append(f"{label} repository.visibility must be public")
        if repository_id != str(api_item.get("id")):
            errors.append(f"{label} repository.platform_repository_id does not match GitHub")
        for github_field, dossier_field in GITHUB_IDENTITY_FIELDS.items():
            if repository.get(dossier_field) != api_item.get(github_field):
                errors.append(
                    f"{label} repository.{dossier_field} does not match GitHub {github_field}"
                )
        for field in GITHUB_MONOTONIC_TIME_FIELDS:
            observed_value = repository.get(field)
            current_value = api_item.get(field)
            observed_time = _parse_datetime(observed_value)
            current_time = _parse_datetime(current_value)
            if observed_value is None and current_value is None:
                continue
            if observed_time is None or current_time is None or current_time < observed_time:
                errors.append(
                    f"{label} repository.{field} is newer than or invalid against GitHub {field}"
                )
        if _canonical_repository_url(repository.get("canonical_url")) != _canonical_repository_url(
            api_item.get("html_url")
        ):
            errors.append(f"{label} repository.canonical_url does not match GitHub html_url")

        expected_api_url = f"https://api.github.com/repositories/{repository_id}"
        repository_api_evidence = [
            item
            for item in dossier.get("evidence", [])
            if isinstance(item, dict) and item.get("source_type") == "repository_api"
        ]
        if not repository_api_evidence:
            errors.append(f"{label} is missing repository_api evidence")
        for evidence in repository_api_evidence:
            if evidence.get("url") != expected_api_url:
                errors.append(
                    f"{label} repository_api evidence must use {expected_api_url}"
                )
        expected_commit_url = (
            f"https://api.github.com/repositories/{repository_id}/commits/"
            f"{repository.get('default_branch_oid')}"
        )
        repository_commit_evidence = [
            item
            for item in dossier.get("evidence", [])
            if isinstance(item, dict) and item.get("source_type") == "repository_commit"
        ]
        if repository.get("default_branch_oid") is not None and not repository_commit_evidence:
            errors.append(f"{label} is missing repository_commit evidence")
        for evidence in repository_commit_evidence:
            if evidence.get("url") != expected_commit_url:
                errors.append(
                    f"{label} repository_commit evidence must use {expected_commit_url}"
                )

        if repository_details_by_id is not None:
            detail = repository_details_by_id.get(repository_id)
            if not isinstance(detail, dict):
                errors.append(f"{label} is missing trusted GitHub repository detail")
            else:
                parent = detail.get("parent")
                expected_parent = str(parent.get("id")) if isinstance(parent, dict) else None
                if repository.get("fork_parent_repository_id") != expected_parent:
                    errors.append(
                        f"{label} repository.fork_parent_repository_id does not match GitHub parent"
                    )
        if default_branch_oids_by_id is not None:
            expected_oid = default_branch_oids_by_id.get(repository_id)
            if repository.get("default_branch_oid") != expected_oid:
                errors.append(
                    f"{label} repository.default_branch_oid does not match GitHub default branch"
                )

    return errors


def fetch_github_enumeration_page(
    since: str,
    *,
    endpoint: str = "https://api.github.com/repositories",
    per_page: int = 100,
    token: str | None = None,
    timeout: float = 30.0,
    max_response_bytes: int = MAX_GITHUB_RESPONSE_BYTES,
) -> list[dict[str, Any]]:
    """Fetch one bounded public-repository enumeration page from GitHub."""

    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or parsed.netloc != "api.github.com" or parsed.path != "/repositories":
        raise ValueError("GitHub enumeration endpoint must be https://api.github.com/repositories")
    if not isinstance(since, str) or not since.isdigit():
        raise ValueError("GitHub enumeration since cursor must be numeric")
    if not isinstance(per_page, int) or isinstance(per_page, bool) or not 1 <= per_page <= 100:
        raise ValueError("GitHub enumeration per_page must be between 1 and 100")

    url = f"{endpoint}?{urlencode({'since': since, 'per_page': per_page})}"
    decoded = _fetch_github_json(
        url,
        token=token,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
    )
    if not isinstance(decoded, list):
        raise ValueError("GitHub enumeration response must be an array")
    return decoded


def _fetch_github_json(
    url: str,
    *,
    token: str | None = None,
    timeout: float = 30.0,
    max_response_bytes: int = MAX_GITHUB_RESPONSE_BYTES,
) -> Any:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "api.github.com":
        raise ValueError("GitHub API URL must use https://api.github.com")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "kai-yuan-da-shu-li-validator/1.0",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        payload = response.read(max_response_bytes + 1)
    if len(payload) > max_response_bytes:
        raise ValueError("GitHub enumeration response exceeds the size limit")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"GitHub enumeration response is invalid JSON: {exc}") from exc
    return decoded


def fetch_github_repository_verification(
    dossiers: list[dict[str, Any]],
    *,
    token: str | None = None,
    timeout: float = 30.0,
) -> tuple[dict[str, dict[str, Any]], dict[str, str | None]]:
    """Fetch trusted repository details and default-branch heads for a batch."""

    details: dict[str, dict[str, Any]] = {}
    branch_oids: dict[str, str | None] = {}
    for dossier in dossiers:
        repository = dossier.get("repository", {})
        repository_id = repository.get("platform_repository_id")
        if not isinstance(repository_id, str) or not repository_id.isdigit():
            raise ValueError("dossier repository id must be numeric before online verification")
        detail_url = f"https://api.github.com/repositories/{repository_id}"
        detail = _fetch_github_json(detail_url, token=token, timeout=timeout)
        if not isinstance(detail, dict) or str(detail.get("id")) != repository_id:
            raise ValueError(f"GitHub repository detail for {repository_id} is invalid")
        details[repository_id] = detail

        default_branch = repository.get("default_branch")
        default_branch_oid = repository.get("default_branch_oid")
        if default_branch is None:
            branch_oids[repository_id] = None
            continue
        if not isinstance(default_branch, str) or not default_branch:
            raise ValueError(f"repository {repository_id} has invalid default_branch")
        if default_branch_oid is None:
            commit_url = (
                f"https://api.github.com/repositories/{repository_id}/commits/"
                f"{quote(default_branch, safe='')}"
            )
            try:
                commit = _fetch_github_json(commit_url, token=token, timeout=timeout)
            except HTTPError as exc:
                if exc.code == 409:
                    exc.close()
                    branch_oids[repository_id] = None
                    continue
                raise
            if (
                not isinstance(commit, dict)
                or not isinstance(commit.get("sha"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", commit["sha"])
            ):
                raise ValueError(
                    f"GitHub default branch commit for {repository_id} is invalid"
                )
            raise ValueError(
                f"repository {repository_id} default_branch_oid is null "
                f"but GitHub default branch has commit {commit['sha']}"
            )
        if not isinstance(default_branch_oid, str) or not re.fullmatch(r"[0-9a-f]{40}", default_branch_oid):
            raise ValueError(f"repository {repository_id} has invalid default_branch_oid")
        compare_url = (
            f"https://api.github.com/repositories/{repository_id}/compare/"
            f"{quote(default_branch_oid, safe='')}...{quote(default_branch, safe='')}"
        )
        comparison = _fetch_github_json(compare_url, token=token, timeout=timeout)
        if not isinstance(comparison, dict) or comparison.get("status") not in {
            "identical",
            "ahead",
        }:
            raise ValueError(
                f"GitHub recorded OID for {repository_id} is outside default branch history"
            )
        branch_oids[repository_id] = default_branch_oid
    return details, branch_oids


def _accepted_history(
    research_dir: Path,
    current_artifact: Path,
    current_manifest: Path,
    errors: list[str],
) -> tuple[set[str], str | None]:
    repository_ids: set[str] = set()
    next_since_values: list[int] = []
    for path in sorted(research_dir.glob("*.jsonl")):
        if path.resolve() == current_artifact.resolve():
            continue
        try:
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError(f"line {line_number} must be an object")
                repository_id = item.get("repository", {}).get("platform_repository_id")
                if not isinstance(repository_id, str) or not repository_id.isdigit():
                    raise ValueError(f"line {line_number} has invalid repository id")
                repository_ids.add(repository_id)
        except (OSError, json.JSONDecodeError, ValueError, AttributeError) as exc:
            errors.append(f"cannot read accepted history {path.name}: {exc}")
    for path in sorted(research_dir.glob("*.manifest.json")):
        if path.resolve() == current_manifest.resolve():
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(item, dict):
                raise ValueError("manifest must be an object")
            cursor = item.get("next_since")
            if not isinstance(cursor, str) or not cursor.isdigit():
                raise ValueError("manifest has invalid next_since")
            next_since_values.append(int(cursor))
            failures = item.get("failures", [])
            if not isinstance(failures, list):
                raise ValueError("manifest failures must be an array")
            for failure in failures:
                repository_id = failure.get("repository_id") if isinstance(failure, dict) else None
                if not isinstance(repository_id, str) or not repository_id.isdigit():
                    raise ValueError("manifest failure has invalid repository id")
                repository_ids.add(repository_id)
        except (OSError, json.JSONDecodeError, ValueError, AttributeError) as exc:
            errors.append(f"cannot read accepted history {path.name}: {exc}")
    latest = str(max(next_since_values)) if next_since_values else None
    return repository_ids, latest


def _is_valid_spdx_expression(expression: Any) -> bool:
    if not isinstance(expression, str) or not expression.strip():
        return False
    try:
        SPDX_LICENSING.parse(expression, simple=True)
    except Exception:
        return False
    info = SPDX_LICENSING.validate(expression, strict=True)
    return all(LICENSE_REF_PATTERN.fullmatch(symbol) for symbol in info.invalid_symbols)


def _validate_dossier_semantics(
    dossier: dict[str, Any],
    index: int,
    taxonomy: dict[str, Any],
    manifest_batch_id: str | None,
) -> list[str]:
    errors: list[str] = []
    label = f"record {index}"

    if dossier.get("batch_id") != manifest_batch_id:
        errors.append(f"{label} batch_id does not match manifest batch_id")

    licensing = dossier.get("licensing", {})
    forbidden = sorted(FORBIDDEN_LICENSE_OBLIGATION_KEYS.intersection(licensing))
    if forbidden:
        errors.append(
            f"{label} contains DeepSeek-authored license obligations: {', '.join(forbidden)}"
        )
    if licensing.get("obligations_source") != "not-provided-by-worker":
        errors.append(f"{label} license obligations must not be supplied by the data worker")

    evidence = dossier.get("evidence", [])
    evidence_ids = [item.get("id") for item in evidence if isinstance(item, dict)]
    duplicate_evidence = sorted(
        str(item) for item, count in Counter(evidence_ids).items() if count > 1
    )
    if duplicate_evidence:
        errors.append(f"{label} has duplicate evidence ids: {', '.join(duplicate_evidence)}")
    known_evidence = set(evidence_ids)
    evidence_source_types = {
        item.get("id"): item.get("source_type")
        for item in evidence
        if isinstance(item, dict)
    }
    evidence_applies_to = {
        item.get("id"): set(item.get("applies_to", []))
        for item in evidence
        if isinstance(item, dict)
    }
    repository = dossier.get("repository", {})
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source_type = item.get("source_type")
        evidence_id = item.get("id")
        for path in item.get("applies_to", []):
            if isinstance(source_type, str) and not _path_supported_by_source(path, source_type):
                errors.append(
                    f"{label} evidence {evidence_id} source type {source_type} cannot support {path}"
                )
        if not _evidence_belongs_to_repository(
            item.get("url"),
            source_type,
            repository.get("platform_repository_id"),
            repository.get("full_name"),
        ):
            errors.append(f"{label} evidence {evidence_id} does not belong to repository")

    required_paths = taxonomy.get("required_field_state_paths", [])
    allowed_paths = set(required_paths)
    field_states = dossier.get("field_states", {})
    for path in field_states:
        if path not in allowed_paths:
            errors.append(f"{label} has uncontrolled field state path {path}")
    for item in evidence:
        if not isinstance(item, dict):
            continue
        for path in item.get("applies_to", []):
            if path not in allowed_paths:
                errors.append(
                    f"{label} evidence {item.get('id')} has uncontrolled applies_to path {path}"
                )
    for path in required_paths:
        value = _nested_value(dossier, path)
        state = field_states.get(path)
        if state is None:
            errors.append(f"{label} missing required field state for {path}")
            continue
        status = state.get("state")
        reference_ids = state.get("evidence_ids", [])
        if status == "unknown":
            if reference_ids:
                errors.append(f"{label} {path} has unknown state but carries evidence")
            if not _value_is_compatible_with_unknown_state(value):
                errors.append(f"{label} {path} has unknown state for a known value")
            continue
        if _value_is_explicitly_unknown(value) and path not in VERIFIED_NULL_PATHS:
            errors.append(f"{label} {path} is empty or unknown but state is {status}")
        if not reference_ids:
            errors.append(f"{label} {path} is non-unknown without evidence")
        if status == "inferred" and path.startswith(NO_INFERENCE_PATH_PREFIXES):
            errors.append(f"{label} {path} must not be inferred")
        if status == "conflicting" and len(set(reference_ids)) < 2:
            errors.append(f"{label} {path} conflicting state needs at least two evidence ids")
        for evidence_id in reference_ids:
            if evidence_id not in known_evidence:
                errors.append(f"{label} {path} references nonexistent evidence id {evidence_id}")
            elif path not in evidence_applies_to.get(evidence_id, set()):
                errors.append(f"{label} evidence {evidence_id} does not declare applies_to {path}")

    field_state_values = [
        state.get("state") for state in field_states.values() if isinstance(state, dict)
    ]
    if "conflicting" in field_state_values:
        expected_record_status = "conflicting"
    elif any(state in {"unknown", "stale"} for state in field_state_values):
        expected_record_status = "unknown"
    else:
        expected_record_status = "complete"
    if dossier.get("record_status") != expected_record_status:
        errors.append(
            f"{label} record_status must be {expected_record_status} for its field_states"
        )

    for source, evidence_id in _collect_reference_ids(dossier):
        if evidence_id not in known_evidence:
            errors.append(f"{label} {source} references nonexistent evidence id {evidence_id}")
            continue
        expected_path = _evidence_parent_path(source)
        if expected_path not in evidence_applies_to.get(evidence_id, set()):
            errors.append(
                f"{label} evidence {evidence_id} does not declare applies_to {expected_path}"
            )

    for dotted_path, taxonomy_key in TAXONOMY_FIELDS.items():
        allowed = set(taxonomy.get(taxonomy_key, []))
        values = _nested_value(dossier, dotted_path)
        if not isinstance(values, list):
            continue
        for value in values:
            if value not in allowed:
                errors.append(f"{label} {dotted_path} contains uncontrolled value {value!r}")

    maintenance_model = _nested_value(dossier, "lifecycle.maintenance_model")
    if maintenance_model not in set(taxonomy.get("maintenance_models", [])):
        errors.append(f"{label} lifecycle.maintenance_model contains uncontrolled value {maintenance_model!r}")
    production_claim = _nested_value(dossier, "quality.production_claim")
    if production_claim not in set(taxonomy.get("production_claims", [])):
        errors.append(f"{label} quality.production_claim contains uncontrolled value {production_claim!r}")

    domains = set(_nested_value(dossier, "classification.domain_ids") or [])
    for subdomain in _nested_value(dossier, "classification.subdomain_ids") or []:
        parent = subdomain.split(":", 1)[0]
        if parent not in domains:
            errors.append(f"{label} subdomain {subdomain!r} has no matching parent domain")

    repository = dossier.get("repository", {})
    for relation_index, relation in enumerate(dossier.get("relations", [])):
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("type")
        for evidence_id in relation.get("evidence_ids", []):
            if evidence_source_types.get(evidence_id) != "repository_api":
                continue
            api_supported = (
                relation_type == "fork_of"
                and repository.get("is_fork") is True
                and relation.get("target_repository_id")
                == repository.get("fork_parent_repository_id")
            )
            if not api_supported:
                errors.append(
                    f"{label} repository_api cannot support relations[{relation_index}] "
                    f"of type {relation_type!r}"
                )
    fork_relations = [
        relation
        for relation in dossier.get("relations", [])
        if isinstance(relation, dict) and relation.get("type") == "fork_of"
    ]
    parent_id = repository.get("fork_parent_repository_id")
    if repository.get("is_fork") is False and (parent_id is not None or fork_relations):
        errors.append(f"{label} fork consistency requires non-forks to have no parent or fork_of relation")
    if repository.get("is_fork") is True:
        if parent_id is None and fork_relations:
            errors.append(f"{label} fork consistency forbids fork_of relation without a known parent")
        if parent_id is not None and (
            len(fork_relations) != 1
            or fork_relations[0].get("target_repository_id") != parent_id
        ):
            errors.append(f"{label} fork consistency requires one fork_of relation matching the parent")

    expressions = [licensing.get("current_expression")]
    expressions.extend(
        item.get("expression")
        for item in licensing.get("version_rules", [])
        if isinstance(item, dict)
    )
    for expression in expressions:
        if expression == "unknown":
            continue
        if not _is_valid_spdx_expression(expression):
            errors.append(f"{label} has invalid SPDX/LicenseRef expression {expression!r}")

    parsed_ranges: list[tuple[str, tuple[Any, ...]]] = []
    range_values = [
        item.get("version_range")
        for item in licensing.get("version_rules", [])
        if isinstance(item, dict)
    ]
    range_values.extend(
        item.get("version_range")
        for item in evidence
        if isinstance(item, dict) and item.get("version_range") is not None
    )
    for version_range in range_values:
        parsed = _parse_version_range(version_range)
        if parsed is None:
            errors.append(f"{label} has invalid license version range {version_range!r}")
        else:
            parsed_ranges.append((version_range, parsed))
    rule_ranges = parsed_ranges[: len(licensing.get("version_rules", []))]
    for left_index, (left_text, left_range) in enumerate(rule_ranges):
        for right_text, right_range in rule_ranges[left_index + 1 :]:
            if _version_ranges_overlap(left_range, right_range):
                errors.append(
                    f"{label} license version ranges overlap: {left_text!r} and {right_text!r}"
                )

    errors.extend(_scan_sensitive(dossier, label))
    return errors


def validate_batch(
    artifact_path: Path | str,
    manifest_path: Path | str,
    *,
    repo_root: Path | str = ROOT,
    contract_root: Path | str | None = None,
    history_root: Path | str | None = None,
    available_repositories: int | None = None,
) -> list[str]:
    """Return all validation errors for one JSONL artifact and its manifest."""

    root = Path(repo_root).resolve()
    artifact = Path(artifact_path)
    manifest_file = Path(manifest_path)
    if not artifact.is_absolute():
        artifact = root / artifact
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file

    errors: list[str] = []
    research_dir = root / "data/quarantine/research"
    accepted_research_dir = (
        Path(history_root).resolve() / "data/quarantine/research"
        if history_root is not None
        else research_dir
    )
    if artifact.is_symlink():
        errors.append("artifact must not be a symbolic link")
    if manifest_file.is_symlink():
        errors.append("manifest must not be a symbolic link")
    if artifact.parent.resolve() != research_dir.resolve():
        errors.append("artifact must be directly inside data/quarantine/research")
    if manifest_file.parent.resolve() != research_dir.resolve():
        errors.append("manifest must be directly inside data/quarantine/research")
    explicit_contract_root = Path(contract_root).resolve() if contract_root is not None else None
    trusted_root = explicit_contract_root or root
    if not (trusted_root / DOSSIER_SCHEMA).exists():
        trusted_root = ROOT
    config_root = explicit_contract_root or root
    dossier_schema = _load_json(trusted_root / DOSSIER_SCHEMA, errors, "dossier schema")
    manifest_schema = _load_json(trusted_root / MANIFEST_SCHEMA, errors, "manifest schema")
    taxonomy = _load_json(trusted_root / TAXONOMY, errors, "taxonomy")
    worker_config = _load_json(config_root / WORKER_CONFIG, errors, "worker config")
    manifest = _load_json(manifest_file, errors, "manifest")

    try:
        artifact_bytes = artifact.read_bytes()
    except FileNotFoundError:
        errors.append(f"artifact is missing: {artifact}")
        return errors
    except OSError as exc:
        errors.append(f"cannot read artifact {artifact}: {exc}")
        return errors

    dossiers: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(artifact_bytes.splitlines(), start=1):
        if not raw_line.strip():
            errors.append(f"artifact line {line_number} is blank")
            continue
        try:
            item = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"artifact line {line_number} is invalid JSON: {exc}")
            continue
        if not isinstance(item, dict):
            errors.append(f"artifact line {line_number} must be a JSON object")
            continue
        dossiers.append(item)

    if not all(isinstance(item, dict) for item in (dossier_schema, manifest_schema, taxonomy, worker_config, manifest)):
        return errors

    errors.extend(_schema_errors(manifest, manifest_schema, "manifest"))
    for index, dossier in enumerate(dossiers, start=1):
        errors.extend(_schema_errors(dossier, dossier_schema, f"record {index}"))
        errors.extend(
            _validate_dossier_semantics(
                dossier,
                index,
                taxonomy,
                manifest.get("batch_id"),
            )
        )

    artifact_info = manifest.get("artifact", {})
    try:
        relative_artifact = artifact.resolve().relative_to(root).as_posix()
    except ValueError:
        relative_artifact = ""
        errors.append("artifact path is outside the repository root")
    if artifact_info.get("path") != relative_artifact:
        errors.append("manifest artifact path does not match the validated artifact")
    if artifact_info.get("bytes") != len(artifact_bytes):
        errors.append("manifest artifact bytes do not match the artifact")
    actual_sha = hashlib.sha256(artifact_bytes).hexdigest()
    if artifact_info.get("sha256") != actual_sha:
        errors.append("manifest artifact sha256 does not match the artifact")

    batch_id = manifest.get("batch_id")
    if artifact.name != f"{batch_id}.jsonl":
        errors.append("artifact filename does not match batch_id")
    if manifest_file.name != f"{batch_id}.manifest.json":
        errors.append("manifest filename does not match batch_id")

    repository_ids = [
        dossier.get("repository", {}).get("platform_repository_id") for dossier in dossiers
    ]
    duplicate_ids = sorted(
        str(item) for item, count in Counter(repository_ids).items() if count > 1
    )
    if duplicate_ids:
        errors.append(f"duplicate repository id: {', '.join(duplicate_ids)}")
    numeric_ids = [int(item) for item in repository_ids if isinstance(item, str) and item.isdigit()]
    if len(numeric_ids) == len(repository_ids) and numeric_ids != sorted(numeric_ids):
        errors.append("repository ids must be in ascending numeric order")

    input_info = manifest.get("input", {})
    queued_ids = input_info.get("repository_ids", [])
    if queued_ids:
        if input_info.get("first_repository_id") != queued_ids[0]:
            errors.append("manifest first_repository_id does not match the first queued id")
        if input_info.get("last_repository_id") != queued_ids[-1]:
            errors.append("manifest last_repository_id does not match the last queued id")
        queued_numeric = [int(item) for item in queued_ids if isinstance(item, str) and item.isdigit()]
        if len(queued_numeric) == len(queued_ids) and queued_numeric != sorted(queued_numeric):
            errors.append("manifest repository_ids must be in ascending numeric order")
        if manifest.get("next_since") != queued_ids[-1]:
            errors.append("next_since must equal the last actual queued repository id")
        since = input_info.get("since")
        if isinstance(since, str) and since.isdigit():
            if any(int(repository_id) <= int(since) for repository_id in queued_ids):
                errors.append("all queued repository ids must be greater than input.since")

    historical_ids, accepted_next_since = _accepted_history(
        accepted_research_dir,
        artifact,
        manifest_file,
        errors,
    )
    repeated_ids = sorted(set(repository_ids).intersection(historical_ids), key=int)
    if repeated_ids:
        errors.append(
            "repository ids already exist in accepted history: " + ", ".join(repeated_ids)
        )
    if accepted_next_since is not None and input_info.get("since") != accepted_next_since:
        errors.append(
            f"manifest input.since must continue accepted next_since={accepted_next_since}"
        )
    if accepted_next_since is None:
        initial_since = worker_config.get("enumeration", {}).get("initial_since")
        if input_info.get("since") != initial_since:
            errors.append(
                f"first batch input.since must equal worker config initial_since={initial_since}"
            )

    failures = manifest.get("failures", [])
    failure_ids = [item.get("repository_id") for item in failures if isinstance(item, dict)]
    if len(failure_ids) != len(set(failure_ids)):
        errors.append("manifest contains duplicate failure repository ids")
    covered_ids = set(repository_ids) | set(failure_ids)
    if set(queued_ids) != covered_ids or len(queued_ids) != len(repository_ids) + len(failure_ids):
        errors.append("queue coverage must equal dossiers plus failures exactly")

    statuses = Counter(dossier.get("record_status") for dossier in dossiers)
    expected_counts = {
        "total": len(queued_ids),
        "complete": statuses["complete"],
        "unknown": statuses["unknown"],
        "conflicting": statuses["conflicting"],
        "failed": len(failure_ids),
        "skipped": 0,
    }
    counts = manifest.get("counts", {})
    for key, expected in expected_counts.items():
        if counts.get(key) != expected:
            errors.append(f"manifest counts.{key} must be {expected}")

    rate_limit = manifest.get("rate_limit", {})
    rate_limit_value = rate_limit.get("limit")
    rate_limit_remaining = rate_limit.get("remaining")
    if (
        isinstance(rate_limit_value, int)
        and not isinstance(rate_limit_value, bool)
        and isinstance(rate_limit_remaining, int)
        and not isinstance(rate_limit_remaining, bool)
        and rate_limit_remaining > rate_limit_value
    ):
        errors.append("manifest rate_limit.remaining must not exceed rate_limit.limit")

    batch_config = worker_config.get("batch", {})
    total = counts.get("total")
    max_repositories = batch_config.get("max_repositories")
    if isinstance(total, int) and isinstance(max_repositories, int) and total > max_repositories:
        errors.append(f"batch total exceeds worker config max_repositories={max_repositories}")
    current_repositories = batch_config.get("current_repositories")
    required_repositories = current_repositories
    if (
        isinstance(available_repositories, int)
        and not isinstance(available_repositories, bool)
        and isinstance(current_repositories, int)
    ):
        required_repositories = min(current_repositories, available_repositories)
    if (
        isinstance(total, int)
        and isinstance(required_repositories, int)
        and total != required_repositories
    ):
        errors.append(
            "batch total must equal worker config "
            f"current_repositories or verified final-page size={required_repositories}"
        )
    max_artifact_bytes = batch_config.get("max_artifact_bytes")
    if isinstance(max_artifact_bytes, int) and len(artifact_bytes) > max_artifact_bytes:
        errors.append(f"artifact exceeds worker config max_artifact_bytes={max_artifact_bytes}")

    expected_versions = {
        "dossier_schema_version": "research-dossier-v1",
        "manifest_schema_version": "research-batch-manifest-v1",
        "taxonomy_version": "research-taxonomy-v1",
    }
    for key, expected in expected_versions.items():
        if worker_config.get(key) != expected:
            errors.append(f"worker config {key} must be {expected}")
    if taxonomy.get("schema_version") != worker_config.get("taxonomy_version"):
        errors.append("worker config taxonomy_version does not match the taxonomy")
    if worker_config.get("status") != "ready":
        errors.append("worker config must have status=ready before accepting a batch")

    errors.extend(_scan_sensitive(manifest, "manifest"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--contract-root",
        type=Path,
        help="trusted root containing schemas, taxonomy, and worker configuration",
    )
    parser.add_argument(
        "--history-root",
        type=Path,
        help="trusted root containing accepted research history",
    )
    parser.add_argument(
        "--verify-github-enumeration",
        action="store_true",
        help="re-fetch the GitHub public-repository page and verify queue provenance",
    )
    args = parser.parse_args()

    github_page: list[dict[str, Any]] | None = None
    github_repository_details: dict[str, dict[str, Any]] | None = None
    github_default_branch_oids: dict[str, str | None] | None = None
    online_errors: list[str] = []
    if args.verify_github_enumeration:
        root = args.repo_root.resolve()
        artifact = args.artifact if args.artifact.is_absolute() else root / args.artifact
        manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dossiers = [
            json.loads(line)
            for line in artifact.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        trusted_root = args.contract_root.resolve() if args.contract_root else root
        config = json.loads((trusted_root / WORKER_CONFIG).read_text(encoding="utf-8"))
        enumeration = config["enumeration"]
        try:
            github_page = fetch_github_enumeration_page(
                manifest["input"]["since"],
                endpoint=enumeration["endpoint"],
                per_page=enumeration["per_page"],
                token=os.environ.get("GITHUB_TOKEN"),
            )
            github_repository_details, github_default_branch_oids = (
                fetch_github_repository_verification(
                    dossiers,
                    token=os.environ.get("GITHUB_TOKEN"),
                )
            )
        except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
            online_errors.append(f"cannot verify GitHub enumeration: {exc}")

    errors = validate_batch(
        args.artifact,
        args.manifest,
        repo_root=args.repo_root,
        contract_root=args.contract_root,
        history_root=args.history_root,
        available_repositories=len(github_page) if github_page is not None else None,
    )
    errors.extend(online_errors)
    if github_page is not None and not errors:
        root = args.repo_root.resolve()
        artifact = args.artifact if args.artifact.is_absolute() else root / args.artifact
        manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dossiers = [
            json.loads(line)
            for line in artifact.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        errors.extend(
            validate_github_enumeration(
                dossiers,
                manifest,
                github_page,
                repository_details_by_id=github_repository_details,
                default_branch_oids_by_id=github_default_branch_oids,
            )
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"validated {args.artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
