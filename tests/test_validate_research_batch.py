import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.validate_research_batch import (
    fetch_github_repository_verification,
    validate_batch,
    validate_github_enumeration,
)


DECISION_VALUES = {
    "repository.platform_repository_id": "1",
    "repository.platform_node_id": "MDEwOlJlcG9zaXRvcnkx",
    "repository.full_name": "mojombo/grit",
    "repository.canonical_url": "https://github.com/mojombo/grit",
    "repository.name_history": [],
    "repository.default_branch": "master",
    "repository.default_branch_oid": "a" * 40,
    "repository.visibility": "public",
    "repository.is_fork": False,
    "repository.fork_parent_repository_id": None,
    "repository.mirror_url": None,
    "repository.archived": False,
    "repository.disabled": False,
    "repository.created_at": "2007-10-29T14:37:16Z",
    "repository.updated_at": "2026-07-22T00:00:00Z",
    "repository.pushed_at": "2010-05-12T00:00:00Z",
    "localized_content.name": {"zh-CN": "Grit", "en": "Grit"},
    "localized_content.summary": {"zh-CN": "代码整理工具。", "en": "A code organization tool."},
    "localized_content.use_when": {"zh-CN": ["需要其明确能力时"], "en": ["Its documented capability is needed"]},
    "localized_content.avoid_when": {"zh-CN": ["需求不匹配时"], "en": ["The requirement does not match"]},
    "classification.domain_ids": ["devtools"],
    "classification.subdomain_ids": ["devtools:lang-tooling"],
    "classification.task_ids": [],
    "classification.capability_ids": [],
    "classification.project_types": ["library"],
    "technology.programming_languages": ["Ruby"],
    "technology.frameworks": [],
    "technology.runtimes": [],
    "technology.protocols": [],
    "technology.data_types": [],
    "delivery.modes": [],
    "delivery.package_formats": [],
    "delivery.orchestrators": [],
    "platforms.operating_systems": [],
    "platforms.execution_targets": [],
    "platforms.cpu_architectures": [],
    "platforms.accelerators": [],
    "natural_language_support.zh-CN.ui": "unknown",
    "natural_language_support.zh-CN.docs": "none",
    "natural_language_support.zh-CN.community": "unknown",
    "natural_language_support.en.ui": "unknown",
    "natural_language_support.en.docs": "full",
    "natural_language_support.en.community": "unknown",
    "licensing.openness": "open-source",
    "licensing.current_expression": "MIT",
    "licensing.version_rules": [
        {"version_range": "*", "expression": "MIT", "evidence_ids": ["ev-license"]}
    ],
    "licensing.additional_terms": [],
    "releases": [],
    "lifecycle.status": "inactive",
    "lifecycle.latest_activity_at": "2010-05-12T00:00:00Z",
    "lifecycle.maintenance_model": "unknown",
    "security.security_policy": "absent",
    "security.advisory_source": "github",
    "security.supported_versions_known": False,
    "quality.maturity": "unknown",
    "quality.production_claim": "unknown",
    "quality.known_limitations": [],
    "relations": [],
}


def _state(value):
    unknown = value in (None, "unknown") or value == []
    if isinstance(value, dict):
        unknown = False
    return {
        "state": "unknown" if unknown else "verified",
        "evidence_ids": [] if unknown else ["ev-api"],
    }


def valid_dossier(repository_id="1"):
    dossier = {
        "schema_version": "research-dossier-v1",
        "batch_id": "github-since-0-0001",
        "record_status": "unknown",
        "observed_at": "2026-07-22T12:00:00Z",
        "repository": {
            "platform": "github",
            "platform_repository_id": repository_id,
            "platform_node_id": "MDEwOlJlcG9zaXRvcnkx",
            "full_name": "mojombo/grit",
            "canonical_url": "https://github.com/mojombo/grit",
            "name_history": [],
            "default_branch": "master",
            "default_branch_oid": "a" * 40,
            "visibility": "public",
            "is_fork": False,
            "fork_parent_repository_id": None,
            "mirror_url": None,
            "archived": False,
            "disabled": False,
            "created_at": "2007-10-29T14:37:16Z",
            "updated_at": "2026-07-22T00:00:00Z",
            "pushed_at": "2010-05-12T00:00:00Z",
        },
        "localized_content": {
            "name": {"zh-CN": "Grit", "en": "Grit"},
            "summary": DECISION_VALUES["localized_content.summary"],
            "use_when": DECISION_VALUES["localized_content.use_when"],
            "avoid_when": DECISION_VALUES["localized_content.avoid_when"],
        },
        "classification": {
            "domain_ids": ["devtools"],
            "subdomain_ids": ["devtools:lang-tooling"],
            "task_ids": [],
            "capability_ids": [],
            "project_types": ["library"],
        },
        "technology": {
            "programming_languages": ["Ruby"],
            "frameworks": [],
            "runtimes": [],
            "protocols": [],
            "data_types": [],
        },
        "delivery": {"modes": [], "package_formats": [], "orchestrators": []},
        "platforms": {
            "operating_systems": [],
            "execution_targets": [],
            "cpu_architectures": [],
            "accelerators": [],
        },
        "natural_language_support": {
            "zh-CN": {"ui": "unknown", "docs": "none", "community": "unknown"},
            "en": {"ui": "unknown", "docs": "full", "community": "unknown"},
        },
        "licensing": {
            "openness": "open-source",
            "current_expression": "MIT",
            "version_rules": [
                {"version_range": "*", "expression": "MIT", "evidence_ids": ["ev-license"]}
            ],
            "additional_terms": [],
            "obligations_source": "not-provided-by-worker",
        },
        "releases": [],
        "lifecycle": {
            "status": "inactive",
            "latest_activity_at": "2010-05-12T00:00:00Z",
            "maintenance_model": "unknown",
        },
        "security": {
            "security_policy": "absent",
            "advisory_source": "github",
            "supported_versions_known": False,
        },
        "quality": {
            "maturity": "unknown",
            "production_claim": "unknown",
            "known_limitations": [],
        },
        "relations": [],
        "evidence": [],
        "field_states": {path: _state(value) for path, value in DECISION_VALUES.items()},
        "worker_notes": [],
    }
    dossier["repository"]["platform_repository_id"] = repository_id
    dossier["field_states"]["repository.platform_repository_id"] = {
        "state": "verified",
        "evidence_ids": ["ev-api"],
    }
    dossier["field_states"]["licensing.version_rules"] = {
        "state": "verified",
        "evidence_ids": ["ev-license"],
    }
    for path in ("repository.fork_parent_repository_id", "repository.mirror_url"):
        dossier["field_states"][path] = {
            "state": "verified",
            "evidence_ids": ["ev-api"],
        }

    evidence_paths = {
        "ev-api": [],
        "ev-branch": [],
        "ev-readme": [],
        "ev-license": [],
        "ev-security": [],
        "ev-advisory": [],
    }
    for path, state in dossier["field_states"].items():
        if state["state"] == "unknown":
            continue
        if path == "repository.default_branch_oid":
            evidence_id = "ev-branch"
        elif path.startswith("repository.") or path == "lifecycle.latest_activity_at":
            evidence_id = "ev-api"
        elif path.startswith("licensing."):
            evidence_id = "ev-license"
        elif path in {"security.security_policy", "security.supported_versions_known"}:
            evidence_id = "ev-security"
        elif path == "security.advisory_source":
            evidence_id = "ev-advisory"
        else:
            evidence_id = "ev-readme"
        state["evidence_ids"] = [evidence_id]
        evidence_paths[evidence_id].append(path)

    common = {
        "retrieved_at": "2026-07-22T12:00:00Z",
        "version_range": None,
        "content_sha256": None,
    }
    dossier["evidence"] = [
        {
            **common,
            "id": "ev-api",
            "url": "https://api.github.com/repositories/1",
            "source_type": "repository_api",
            "applies_to": evidence_paths["ev-api"],
            "fact": "GitHub repository metadata.",
        },
        {
            **common,
            "id": "ev-branch",
            "url": "https://api.github.com/repositories/1/commits/" + "a" * 40,
            "source_type": "repository_commit",
            "applies_to": evidence_paths["ev-branch"],
            "fact": "GitHub default branch head commit.",
        },
        {
            **common,
            "id": "ev-readme",
            "url": "https://raw.githubusercontent.com/mojombo/grit/" + "a" * 40 + "/README.md",
            "source_type": "readme",
            "applies_to": evidence_paths["ev-readme"],
            "fact": "Project README facts.",
            "content_sha256": "c" * 64,
        },
        {
            **common,
            "id": "ev-license",
            "url": "https://raw.githubusercontent.com/mojombo/grit/" + "a" * 40 + "/LICENSE",
            "source_type": "license_file",
            "applies_to": evidence_paths["ev-license"],
            "version_range": "*",
            "fact": "The repository license file states the MIT license.",
            "content_sha256": "b" * 64,
        },
        {
            **common,
            "id": "ev-security",
            "url": "https://raw.githubusercontent.com/mojombo/grit/" + "a" * 40 + "/SECURITY.md",
            "source_type": "security_policy",
            "applies_to": evidence_paths["ev-security"],
            "fact": "Repository security policy facts.",
            "content_sha256": "d" * 64,
        },
        {
            **common,
            "id": "ev-advisory",
            "url": "https://github.com/mojombo/grit/security/advisories",
            "source_type": "advisory",
            "applies_to": evidence_paths["ev-advisory"],
            "fact": "GitHub security advisory surface.",
        },
    ]
    next(item for item in dossier["evidence"] if item["id"] == "ev-api")["url"] = (
        f"https://api.github.com/repositories/{repository_id}"
    )
    next(item for item in dossier["evidence"] if item["id"] == "ev-branch")["url"] = (
        f"https://api.github.com/repositories/{repository_id}/commits/" + "a" * 40
    )
    return dossier


def valid_github_page():
    return [
        {
            "id": 1,
            "node_id": "MDEwOlJlcG9zaXRvcnkx",
            "full_name": "mojombo/grit",
            "html_url": "https://github.com/mojombo/grit",
            "default_branch": "master",
            "private": False,
            "fork": False,
            "mirror_url": None,
            "archived": False,
            "disabled": False,
            "created_at": "2007-10-29T14:37:16Z",
            "updated_at": "2026-07-22T00:00:00Z",
            "pushed_at": "2010-05-12T00:00:00Z",
        }
    ]


def write_worker_config(root: Path, **batch_overrides):
    config = {
        "schema_version": "research-worker-config-v1",
        "status": "ready",
        "dossier_schema_version": "research-dossier-v1",
        "manifest_schema_version": "research-batch-manifest-v1",
        "taxonomy_version": "research-taxonomy-v1",
        "batch": {
            "initial_repositories": 20,
            "current_repositories": 20,
            "max_repositories": 100,
            "max_artifact_bytes": 5 * 1024 * 1024,
            "successful_batches_before_increase": 3,
        },
        "enumeration": {
            "source": "github-public-repositories",
            "endpoint": "https://api.github.com/repositories",
            "per_page": 100,
            "initial_since": "0",
        },
        "write_policy": {
            "allowed_globs": [
                "data/quarantine/research/*.jsonl",
                "data/quarantine/research/*.manifest.json",
            ]
        },
    }
    config["batch"].update(batch_overrides)
    path = root / "data/quarantine/research/worker-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def write_batch(root: Path, dossiers, repository_ids=None):
    batch_id = "github-since-0-0001"
    artifact = root / "data/quarantine/research" / f"{batch_id}.jsonl"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in dossiers),
        encoding="utf-8",
    )
    ids = repository_ids or [item["repository"]["platform_repository_id"] for item in dossiers]
    write_worker_config(root, current_repositories=len(ids))
    statuses = [item["record_status"] for item in dossiers]
    manifest = {
        "schema_version": "research-batch-manifest-v1",
        "batch_id": batch_id,
        "created_at": "2026-07-22T12:30:00Z",
        "input": {
            "source": "github-public-repositories",
            "since": "0",
            "repository_ids": ids,
            "first_repository_id": ids[0],
            "last_repository_id": ids[-1],
        },
        "counts": {
            "total": len(ids),
            "complete": statuses.count("complete"),
            "unknown": statuses.count("unknown"),
            "conflicting": statuses.count("conflicting"),
            "failed": len(ids) - len(dossiers),
            "skipped": 0,
        },
        "artifact": {
            "path": artifact.relative_to(root).as_posix(),
            "bytes": artifact.stat().st_size,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        },
        "rate_limit": {
            "resource": "core",
            "limit": 5000,
            "remaining": 4900,
            "reset_at": "2026-07-22T13:00:00Z",
            "observed_at": "2026-07-22T12:30:00Z",
        },
        "next_since": ids[-1],
        "failures": [],
        "worker": {
            "model_role": "deepseek-data-worker",
            "program_version": "deepseek-data-worker-v1",
            "run_id": "test-run",
        },
    }
    manifest_path = artifact.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return artifact, manifest_path


class ValidateResearchBatchTests(unittest.TestCase):
    def test_accepts_manifest_operational_checkpoint_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            self.assertEqual(validate_batch(artifact, manifest, repo_root=root), [])

    def test_accepts_failure_attempt_count_and_rejects_missing_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest_path = write_batch(
                root,
                [valid_dossier()],
                repository_ids=["1", "26"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["failures"] = [
                {
                    "repository_id": "26",
                    "reason": "http-timeout",
                    "retry_after": "2026-07-22T13:00:00Z",
                    "attempts": 3,
                }
            ]
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            self.assertEqual(validate_batch(artifact, manifest_path, repo_root=root), [])

            del manifest["failures"][0]["attempts"]
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            errors = validate_batch(artifact, manifest_path, repo_root=root)
            self.assertTrue(any("attempts" in error for error in errors), errors)

    def test_rejects_rate_limit_remaining_greater_than_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest_path = write_batch(root, [valid_dossier()])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rate_limit"]["remaining"] = 5001
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            errors = validate_batch(artifact, manifest_path, repo_root=root)
            self.assertTrue(any("rate_limit.remaining" in error for error in errors), errors)

    def test_accepts_valid_evidence_closed_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            self.assertEqual(validate_batch(artifact, manifest, repo_root=root), [])

    def test_rejects_duplicate_repository_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier(), valid_dossier()])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("duplicate repository id" in error for error in errors), errors)

    def test_rejects_non_unknown_field_without_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["field_states"]["licensing.current_expression"]["evidence_ids"] = []
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("licensing.current_expression" in error for error in errors), errors)

    def test_rejects_manifest_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest_path = write_batch(root, [valid_dossier()])
            manifest = json.loads(manifest_path.read_text())
            manifest["artifact"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest) + "\n")
            errors = validate_batch(artifact, manifest_path, repo_root=root)
            self.assertTrue(any("sha256" in error for error in errors), errors)

    def test_rejects_queue_ids_not_covered_by_records_or_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()], repository_ids=["1", "26"])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("queue coverage" in error for error in errors), errors)

    def test_rejects_malformed_controlled_enum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["licensing"]["openness"] = "mostly-open"
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("openness" in error for error in errors), errors)

    def test_rejects_missing_required_field_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            del dossier["field_states"]["technology.programming_languages"]
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("technology.programming_languages" in error for error in errors), errors)

    def test_rejects_unknown_state_that_carries_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["field_states"]["technology.frameworks"] = {
                "state": "unknown",
                "evidence_ids": ["ev-api"],
            }
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("unknown state" in error for error in errors), errors)

    def test_rejects_unknown_state_for_known_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["field_states"]["technology.programming_languages"] = {
                "state": "unknown",
                "evidence_ids": [],
            }
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("known value" in error for error in errors), errors)

    def test_accepts_verified_empty_list_as_known_none(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["field_states"]["technology.frameworks"] = {
                "state": "verified",
                "evidence_ids": ["ev-readme"],
            }
            next(item for item in dossier["evidence"] if item["id"] == "ev-readme")[
                "applies_to"
            ].append("technology.frameworks")
            artifact, manifest = write_batch(root, [dossier])
            self.assertEqual(validate_batch(artifact, manifest, repo_root=root), [])

    def test_rejects_nonexistent_evidence_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["field_states"]["technology.programming_languages"] = {
                "state": "verified",
                "evidence_ids": ["ev-missing"],
            }
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("ev-missing" in error for error in errors), errors)

    def test_rejects_item_evidence_that_does_not_apply_to_the_item(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["relations"] = [
                {"type": "depends_on", "target_repository_id": "26", "evidence_ids": ["ev-api"]}
            ]
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("does not declare applies_to relations" in error for error in errors), errors)

    def test_rejects_empty_item_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["releases"] = [
                {
                    "version": "1.0.0",
                    "channel": "stable",
                    "released_at": "2026-07-22T00:00:00Z",
                    "support": "supported",
                    "evidence_ids": [],
                }
            ]
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("evidence_ids" in error for error in errors), errors)

    def test_rejects_deepseek_authored_license_obligations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["licensing"]["commercial_use"] = "allowed"
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("license obligations" in error for error in errors), errors)

    def test_rejects_batch_over_configured_repository_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(
                root,
                [valid_dossier("1"), valid_dossier("26")],
            )
            write_worker_config(root, current_repositories=2, max_repositories=1)
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("max_repositories" in error for error in errors), errors)

    def test_rejects_artifact_over_configured_byte_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            write_worker_config(root, max_artifact_bytes=1)
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("max_artifact_bytes" in error for error in errors), errors)

    def test_rejects_nested_batch_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            nested = artifact.parent / "nested"
            nested.mkdir()
            nested_artifact = nested / artifact.name
            nested_manifest = nested / manifest.name
            artifact.rename(nested_artifact)
            manifest.rename(nested_manifest)
            errors = validate_batch(nested_artifact, nested_manifest, repo_root=root)
            self.assertTrue(any("directly inside" in error for error in errors), errors)

    def test_rejects_symlinked_batch_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            real_artifact = artifact.with_name("real.jsonl")
            artifact.rename(real_artifact)
            artifact.symlink_to(real_artifact.name)
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("symbolic link" in error for error in errors), errors)

    def test_rejects_secret_or_private_path_in_worker_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["worker_notes"].append("debug file: /Users/example/.config/private.txt")
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("sensitive value" in error for error in errors), errors)

    def test_rejects_batch_not_equal_to_current_configured_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            write_worker_config(root, current_repositories=20)
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("current_repositories" in error for error in errors), errors)

    def test_accepts_short_final_page_when_online_enumeration_confirms_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            write_worker_config(root, current_repositories=20)
            self.assertEqual(
                validate_batch(
                    artifact,
                    manifest,
                    repo_root=root,
                    available_repositories=1,
                ),
                [],
            )

    def test_rejects_batch_while_worker_config_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            config_path = root / "data/quarantine/research/worker-config.json"
            config = json.loads(config_path.read_text())
            config["status"] = "blocked"
            config_path.write_text(json.dumps(config) + "\n")
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("status=ready" in error for error in errors), errors)

    def test_rejects_record_status_inconsistent_with_field_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["record_status"] = "complete"
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("record_status" in error for error in errors), errors)

    def test_rejects_uncontrolled_taxonomy_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["technology"]["programming_languages"] = ["Rubyish"]
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("uncontrolled value" in error for error in errors), errors)

    def test_rejects_uncontrolled_field_state_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["field_states"]["classification.made_up"] = {
                "state": "verified",
                "evidence_ids": ["ev-api"],
            }
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("uncontrolled field state path" in error for error in errors), errors)

    def test_rejects_uncontrolled_evidence_applies_to_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["evidence"][0]["applies_to"].append("classification.made_up")
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("uncontrolled applies_to" in error for error in errors), errors)

    def test_rejects_repository_id_already_present_in_accepted_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            prior = artifact.parent / "github-prior.jsonl"
            prior.write_text(json.dumps(valid_dossier()) + "\n", encoding="utf-8")
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("accepted history" in error for error in errors), errors)

    def test_rejects_malformed_historical_dossier_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            prior = artifact.parent / "github-prior.jsonl"
            prior.write_text("[]\n", encoding="utf-8")
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("accepted history" in error for error in errors), errors)

    def test_rejects_malformed_historical_manifest_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            prior = artifact.parent / "github-prior.manifest.json"
            prior.write_text("[]\n", encoding="utf-8")
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("accepted history" in error for error in errors), errors)

    def test_rejects_since_cursor_not_continuing_accepted_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier("26")])
            prior = artifact.parent / "github-prior.manifest.json"
            prior.write_text(json.dumps({"next_since": "1"}) + "\n", encoding="utf-8")
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("accepted next_since=1" in error for error in errors), errors)

    def test_rejects_first_batch_not_starting_at_configured_initial_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest_path = write_batch(root, [valid_dossier()])
            manifest = json.loads(manifest_path.read_text())
            manifest["input"]["since"] = "99"
            manifest_path.write_text(json.dumps(manifest) + "\n")
            errors = validate_batch(artifact, manifest_path, repo_root=root)
            self.assertTrue(any("initial_since=0" in error for error in errors), errors)

    def test_rejects_queued_id_not_greater_than_since(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest_path = write_batch(root, [valid_dossier()])
            manifest = json.loads(manifest_path.read_text())
            manifest["input"]["since"] = "1"
            manifest_path.write_text(json.dumps(manifest) + "\n")
            config_path = root / "data/quarantine/research/worker-config.json"
            config = json.loads(config_path.read_text())
            config["enumeration"]["initial_since"] = "1"
            config_path.write_text(json.dumps(config) + "\n")
            errors = validate_batch(artifact, manifest_path, repo_root=root)
            self.assertTrue(any("greater than input.since" in error for error in errors), errors)

    def test_rejects_id_already_present_as_historical_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier("26")])
            prior = artifact.parent / "github-prior.manifest.json"
            prior.write_text(
                json.dumps({"next_since": "1", "failures": [{"repository_id": "26"}]}) + "\n",
                encoding="utf-8",
            )
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("accepted history" in error for error in errors), errors)

    def test_uses_trusted_history_root_instead_of_candidate_history(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            candidate = workspace / "candidate"
            trusted_history = workspace / "trusted-history"
            artifact, manifest_path = write_batch(candidate, [valid_dossier("26")])
            manifest = json.loads(manifest_path.read_text())
            manifest["input"]["since"] = "1"
            manifest_path.write_text(json.dumps(manifest) + "\n")

            candidate_prior = artifact.parent / "candidate-only.manifest.json"
            candidate_prior.write_text(
                json.dumps({"next_since": "999", "failures": []}) + "\n",
                encoding="utf-8",
            )
            trusted_dir = trusted_history / "data/quarantine/research"
            trusted_dir.mkdir(parents=True)
            (trusted_dir / "accepted.manifest.json").write_text(
                json.dumps({"next_since": "1", "failures": []}) + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                validate_batch(
                    artifact,
                    manifest_path,
                    repo_root=candidate,
                    history_root=trusted_history,
                ),
                [],
            )

    def test_accepts_verified_null_for_confirmed_absent_fork_and_mirror(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, manifest = write_batch(root, [valid_dossier()])
            self.assertEqual(validate_batch(artifact, manifest, repo_root=root), [])

    def test_rejects_inferred_license_or_security_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ("licensing.current_expression", "security.security_policy"):
                dossier = valid_dossier()
                dossier["field_states"][path]["state"] = "inferred"
                artifact, manifest = write_batch(root, [dossier])
                errors = validate_batch(artifact, manifest, repo_root=root)
                self.assertTrue(any("must not be inferred" in error for error in errors), errors)

    def test_rejects_conflicting_fact_with_fewer_than_two_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["field_states"]["licensing.current_expression"]["state"] = "conflicting"
            dossier["record_status"] = "conflicting"
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("at least two evidence" in error for error in errors), errors)

    def test_rejects_invalid_spdx_expression(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["licensing"]["current_expression"] = "Whatever License"
            dossier["licensing"]["version_rules"][0]["expression"] = "Whatever License"
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("SPDX" in error for error in errors), errors)

    def test_rejects_evidence_source_type_that_cannot_support_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            state = dossier["field_states"]["localized_content.summary"]
            state["evidence_ids"] = ["ev-api"]
            next(item for item in dossier["evidence"] if item["id"] == "ev-api")[
                "applies_to"
            ].append("localized_content.summary")
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("cannot support localized_content.summary" in error for error in errors), errors)

    def test_repository_api_cannot_replace_commit_or_name_history_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ("repository.default_branch_oid", "repository.name_history"):
                with self.subTest(path=path):
                    dossier = valid_dossier()
                    dossier["field_states"][path] = {
                        "state": "verified",
                        "evidence_ids": ["ev-api"],
                    }
                    next(item for item in dossier["evidence"] if item["id"] == "ev-api")[
                        "applies_to"
                    ].append(path)
                    artifact, manifest = write_batch(root, [dossier])
                    errors = validate_batch(artifact, manifest, repo_root=root)
                    self.assertTrue(any(f"cannot support {path}" in error for error in errors), errors)

    def test_rejects_alternative_relation_supported_only_by_repository_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["relations"] = [
                {
                    "type": "alternative_to",
                    "target_repository_id": "26",
                    "evidence_ids": ["ev-api"],
                }
            ]
            dossier["field_states"]["relations"] = {
                "state": "verified",
                "evidence_ids": ["ev-api"],
            }
            next(item for item in dossier["evidence"] if item["id"] == "ev-api")[
                "applies_to"
            ].append("relations")
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(
                any("repository_api cannot support relations" in error for error in errors),
                errors,
            )

    def test_accepts_fork_relation_supported_by_matching_repository_api_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["repository"]["is_fork"] = True
            dossier["repository"]["fork_parent_repository_id"] = "26"
            dossier["relations"] = [
                {
                    "type": "fork_of",
                    "target_repository_id": "26",
                    "evidence_ids": ["ev-api"],
                }
            ]
            dossier["field_states"]["relations"] = {
                "state": "verified",
                "evidence_ids": ["ev-api"],
            }
            next(item for item in dossier["evidence"] if item["id"] == "ev-api")[
                "applies_to"
            ].append("relations")
            artifact, manifest = write_batch(root, [dossier])
            self.assertEqual(validate_batch(artifact, manifest, repo_root=root), [])

    def test_rejects_mirror_relation_supported_only_by_repository_api_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["repository"]["mirror_url"] = "https://github.com/other/source"
            dossier["relations"] = [
                {
                    "type": "mirror_of",
                    "target_repository_id": "26",
                    "evidence_ids": ["ev-api"],
                }
            ]
            dossier["field_states"]["relations"] = {
                "state": "verified",
                "evidence_ids": ["ev-api"],
            }
            next(item for item in dossier["evidence"] if item["id"] == "ev-api")[
                "applies_to"
            ].append("relations")
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(
                any("repository_api cannot support relations" in error for error in errors),
                errors,
            )

    def test_rejects_repository_bound_evidence_from_another_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            next(item for item in dossier["evidence"] if item["id"] == "ev-license")[
                "url"
            ] = "https://raw.githubusercontent.com/other/project/" + "a" * 40 + "/LICENSE"
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("does not belong to repository" in error for error in errors), errors)

    def test_rejects_invalid_or_overlapping_license_version_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["licensing"]["version_rules"] = [
                {"version_range": ">=1", "expression": "MIT", "evidence_ids": ["ev-license"]},
                {"version_range": ">=1.0.0 <2.0.0", "expression": "Apache-2.0", "evidence_ids": ["ev-license"]},
            ]
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("version range" in error for error in errors), errors)

            dossier = valid_dossier()
            dossier["licensing"]["version_rules"] = [
                {"version_range": ">=1.0.0 <3.0.0", "expression": "MIT", "evidence_ids": ["ev-license"]},
                {"version_range": ">=2.0.0 <4.0.0", "expression": "Apache-2.0", "evidence_ids": ["ev-license"]},
            ]
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("overlap" in error for error in errors), errors)

    def test_accepts_github_page_matching_queue_and_repository_identity(self):
        dossier = valid_dossier()
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        self.assertEqual(validate_github_enumeration([dossier], manifest, valid_github_page()), [])

    def test_rejects_queue_not_matching_github_enumeration_page(self):
        dossier = valid_dossier("999")
        dossier["repository"]["platform_repository_id"] = "999"
        manifest = {"input": {"since": "0", "repository_ids": ["999"]}}
        errors = validate_github_enumeration([dossier], manifest, valid_github_page())
        self.assertTrue(any("enumeration sequence" in error for error in errors), errors)

    def test_rejects_repository_identity_not_matching_github_page(self):
        dossier = valid_dossier()
        dossier["repository"]["full_name"] = "wrong/name"
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        errors = validate_github_enumeration([dossier], manifest, valid_github_page())
        self.assertTrue(any("repository.full_name" in error for error in errors), errors)

    def test_rejects_repository_api_evidence_for_different_id(self):
        dossier = valid_dossier()
        dossier["evidence"][0]["url"] = "https://api.github.com/repositories/999"
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        errors = validate_github_enumeration([dossier], manifest, valid_github_page())
        self.assertTrue(any("repository_api evidence" in error for error in errors), errors)

    def test_rejects_private_repository_enumeration_item(self):
        dossier = valid_dossier()
        page = valid_github_page()
        page[0]["private"] = True
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        errors = validate_github_enumeration([dossier], manifest, page)
        self.assertTrue(any("not public" in error for error in errors), errors)

    def test_rejects_each_mismatched_github_identity_field(self):
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        mutations = {
            "node_id": "wrong-node",
            "default_branch": "wrong-branch",
            "fork": True,
            "mirror_url": "https://example.com/mirror.git",
            "archived": True,
            "disabled": True,
            "created_at": "2020-01-01T00:00:00Z",
        }
        for github_field, replacement in mutations.items():
            with self.subTest(github_field=github_field):
                page = valid_github_page()
                page[0][github_field] = replacement
                errors = validate_github_enumeration([valid_dossier()], manifest, page)
                self.assertTrue(any("does not match GitHub" in error for error in errors), errors)

    def test_accepts_github_updated_and_pushed_times_newer_than_observation(self):
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        page = valid_github_page()
        page[0]["updated_at"] = "2026-07-22T12:01:00Z"
        page[0]["pushed_at"] = "2026-07-22T12:01:00Z"
        self.assertEqual(validate_github_enumeration([valid_dossier()], manifest, page), [])

    def test_accepts_null_github_pushed_at_when_both_values_are_null(self):
        dossier = valid_dossier()
        dossier["repository"]["pushed_at"] = None
        dossier["field_states"]["repository.pushed_at"] = {
            "state": "unknown",
            "evidence_ids": [],
        }
        next(item for item in dossier["evidence"] if item["id"] == "ev-api")[
            "applies_to"
        ].remove("repository.pushed_at")
        page = valid_github_page()
        page[0]["pushed_at"] = None
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        self.assertEqual(validate_github_enumeration([dossier], manifest, page), [])

    def test_rejects_forged_default_branch_oid_against_github_commit(self):
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        errors = validate_github_enumeration(
            [valid_dossier()],
            manifest,
            valid_github_page(),
            repository_details_by_id={"1": {"fork": False, "parent": None}},
            default_branch_oids_by_id={"1": "b" * 40},
        )
        self.assertTrue(any("default_branch_oid" in error for error in errors), errors)

    def test_rejects_forged_fork_parent_against_github_repository_detail(self):
        dossier = valid_dossier()
        dossier["repository"]["is_fork"] = True
        dossier["repository"]["fork_parent_repository_id"] = "999"
        page = valid_github_page()
        page[0]["fork"] = True
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        errors = validate_github_enumeration(
            [dossier],
            manifest,
            page,
            repository_details_by_id={"1": {"fork": True, "parent": {"id": 26}}},
            default_branch_oids_by_id={"1": "a" * 40},
        )
        self.assertTrue(any("fork_parent_repository_id" in error for error in errors), errors)

    def test_rejects_nonfork_with_parent_or_fork_relation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dossier = valid_dossier()
            dossier["repository"]["fork_parent_repository_id"] = "26"
            dossier["relations"] = [
                {"type": "fork_of", "target_repository_id": "26", "evidence_ids": ["ev-api"]}
            ]
            dossier["field_states"]["relations"] = {
                "state": "verified",
                "evidence_ids": ["ev-api"],
            }
            next(item for item in dossier["evidence"] if item["id"] == "ev-api")[
                "applies_to"
            ].append("relations")
            artifact, manifest = write_batch(root, [dossier])
            errors = validate_batch(artifact, manifest, repo_root=root)
            self.assertTrue(any("fork consistency" in error for error in errors), errors)

    def test_fetches_repository_detail_and_default_branch_oid_for_every_dossier(self):
        requested_urls = []

        def fake_fetch(url, *, token=None, timeout=30.0, max_response_bytes=10 * 1024 * 1024):
            requested_urls.append(url)
            if url == "https://api.github.com/repositories/1":
                return {"id": 1, "fork": False, "parent": None}
            if url == "https://api.github.com/repositories/1/compare/" + "a" * 40 + "...master":
                return {"status": "identical"}
            raise AssertionError(url)

        with patch("scripts.validate_research_batch._fetch_github_json", side_effect=fake_fetch):
            details, oids = fetch_github_repository_verification(
                [valid_dossier()], token="not-a-real-token"
            )

        self.assertEqual(details, {"1": {"id": 1, "fork": False, "parent": None}})
        self.assertEqual(oids, {"1": "a" * 40})
        self.assertEqual(
            requested_urls,
            [
                "https://api.github.com/repositories/1",
                "https://api.github.com/repositories/1/compare/" + "a" * 40 + "...master",
            ],
        )

    def test_rejects_recorded_oid_outside_default_branch_history(self):
        def fake_fetch(url, **kwargs):
            if url == "https://api.github.com/repositories/1":
                return {"id": 1, "fork": False, "parent": None}
            return {"status": "diverged"}

        with patch("scripts.validate_research_batch._fetch_github_json", side_effect=fake_fetch):
            with self.assertRaisesRegex(ValueError, "default branch history"):
                fetch_github_repository_verification([valid_dossier()])

    def test_skips_default_branch_commit_request_when_branch_is_unknown(self):
        dossier = valid_dossier()
        dossier["repository"]["default_branch"] = None
        dossier["repository"]["default_branch_oid"] = None
        requested_urls = []

        def fake_fetch(url, **kwargs):
            requested_urls.append(url)
            return {"id": 1, "fork": False, "parent": None}

        with patch("scripts.validate_research_batch._fetch_github_json", side_effect=fake_fetch):
            details, oids = fetch_github_repository_verification([dossier])

        self.assertEqual(details["1"]["id"], 1)
        self.assertEqual(oids, {"1": None})
        self.assertEqual(requested_urls, ["https://api.github.com/repositories/1"])

    def test_accepts_empty_repository_without_default_branch_oid_request(self):
        dossier = valid_dossier()
        dossier["repository"]["default_branch_oid"] = None
        requested_urls = []

        def fake_fetch(url, **kwargs):
            requested_urls.append(url)
            if url == "https://api.github.com/repositories/1":
                return {"id": 1, "fork": False, "parent": None, "size": 0}
            raise HTTPError(url, 409, "Git Repository is empty.", {}, None)

        with patch("scripts.validate_research_batch._fetch_github_json", side_effect=fake_fetch):
            details, oids = fetch_github_repository_verification([dossier])

        self.assertEqual(details["1"]["size"], 0)
        self.assertEqual(oids, {"1": None})
        self.assertEqual(
            requested_urls,
            [
                "https://api.github.com/repositories/1",
                "https://api.github.com/repositories/1/commits/master",
            ],
        )

    def test_rejects_null_default_branch_oid_when_size_zero_repository_has_commits(self):
        dossier = valid_dossier()
        dossier["repository"]["default_branch_oid"] = None

        def fake_fetch(url, **kwargs):
            if url == "https://api.github.com/repositories/1":
                return {"id": 1, "fork": False, "parent": None, "size": 0}
            if url == "https://api.github.com/repositories/1/commits/master":
                return {"sha": "b" * 40}
            raise AssertionError(url)

        with patch("scripts.validate_research_batch._fetch_github_json", side_effect=fake_fetch):
            with self.assertRaisesRegex(ValueError, "default_branch_oid is null"):
                fetch_github_repository_verification([dossier])

    def test_rejects_repository_commit_evidence_for_wrong_oid(self):
        dossier = valid_dossier()
        next(item for item in dossier["evidence"] if item["id"] == "ev-branch")[
            "url"
        ] = "https://api.github.com/repositories/1/commits/" + "b" * 40
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        errors = validate_github_enumeration([dossier], manifest, valid_github_page())
        self.assertTrue(any("repository_commit evidence" in error for error in errors), errors)

    def test_rejects_github_updated_or_pushed_time_older_than_observation(self):
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        for field in ("updated_at", "pushed_at"):
            with self.subTest(field=field):
                page = valid_github_page()
                page[0][field] = "2009-01-01T00:00:00Z"
                errors = validate_github_enumeration([valid_dossier()], manifest, page)
                self.assertTrue(any(f"repository.{field}" in error for error in errors), errors)

    def test_rejects_truncated_github_page(self):
        manifest = {"input": {"since": "0", "repository_ids": ["1", "26"]}}
        errors = validate_github_enumeration([valid_dossier()], manifest, valid_github_page())
        self.assertTrue(any("shorter than the manifest queue" in error for error in errors), errors)

    def test_rejects_non_array_github_response(self):
        manifest = {"input": {"since": "0", "repository_ids": ["1"]}}
        errors = validate_github_enumeration([valid_dossier()], manifest, {"id": 1})
        self.assertTrue(any("must be an array" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
