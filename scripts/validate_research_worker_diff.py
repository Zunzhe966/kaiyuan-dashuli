#!/usr/bin/env python3
"""Enforce the file boundary for DeepSeek research-batch pull requests."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
WORKER_CONFIG = ROOT / "data/quarantine/research/worker-config.json"


def validate_changed_files(
    changed_files: list[tuple[str, str]],
    branch_name: str,
    allowed_globs: list[str],
) -> tuple[list[str], list[tuple[str, str]]]:
    errors: list[str] = []
    pairs: list[tuple[str, str]] = []

    if not branch_name.startswith("data/research-"):
        errors.append("research worker PR branch must start with data/research-")

    if not changed_files:
        errors.append("research worker PR must add at least one batch pair")

    allowed_patterns = [PurePosixPath(pattern) for pattern in allowed_globs]
    for status, path in changed_files:
        if status != "A":
            errors.append(f"research worker PR may only add new files, got {status} for {path}")
        candidate = PurePosixPath(path)
        if not any(
            candidate.parent == pattern.parent
            and fnmatch.fnmatchcase(candidate.name, pattern.name)
            for pattern in allowed_patterns
        ):
            errors.append(f"changed path is outside worker allowlist: {path}")

    paths_by_batch: dict[str, dict[str, str]] = {}
    for _, path in changed_files:
        if path.endswith(".manifest.json"):
            batch_id = Path(path).name.removesuffix(".manifest.json")
            kind = "manifest"
        elif path.endswith(".jsonl"):
            batch_id = Path(path).name.removesuffix(".jsonl")
            kind = "artifact"
        else:
            continue
        batch_paths = paths_by_batch.setdefault(batch_id, {})
        if kind in batch_paths:
            errors.append(f"research worker PR has duplicate {kind} for batch {batch_id}")
        batch_paths[kind] = path

    for batch_id, batch_paths in sorted(paths_by_batch.items()):
        if set(batch_paths) != {"artifact", "manifest"}:
            errors.append(f"batch {batch_id} must contain one JSONL artifact and one manifest")
            continue
        pairs.append((batch_paths["artifact"], batch_paths["manifest"]))

    return errors, pairs


def validate_commit_batches(
    commits: list[tuple[str, list[tuple[str, str]]]],
    allowed_globs: list[str],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Require every accumulation commit to add one immutable batch pair."""

    errors: list[str] = []
    ordered_pairs: list[tuple[str, str]] = []
    for index, (subject, changed_files) in enumerate(commits, start=1):
        commit_errors, pairs = validate_changed_files(
            changed_files,
            "data/research-commit",
            allowed_globs,
        )
        errors.extend(f"commit {index}: {error}" for error in commit_errors)
        if len(pairs) != 1:
            errors.append(f"commit {index} must add exactly one batch pair")
            continue
        batch_id = Path(pairs[0][0]).name.removesuffix(".jsonl")
        expected_subject = f"data: research batch {batch_id}"
        if subject != expected_subject:
            errors.append(f"commit {index} subject must be: {expected_subject}")
        ordered_pairs.extend(pairs)

    if len(set(ordered_pairs)) != len(ordered_pairs):
        errors.append("accumulation history contains a duplicate batch pair")
    return errors, ordered_pairs


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _parse_name_status(output: str) -> list[tuple[str, str]]:
    changed: list[tuple[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0][0]
        path = parts[-1]
        changed.append((status, path))
    return changed


def _changed_files(repo_root: Path, base: str, head: str) -> list[tuple[str, str]]:
    return _parse_name_status(
        _git(repo_root, "diff", "--name-status", "--diff-filter=ACDMRTUXB", f"{base}...{head}")
    )


def _commit_changes(
    repo_root: Path,
    base: str,
    head: str,
) -> tuple[list[str], list[tuple[str, list[tuple[str, str]]]]]:
    errors: list[str] = []
    commits: list[tuple[str, list[tuple[str, str]]]] = []
    commit_ids = _git(repo_root, "rev-list", "--reverse", f"{base}..{head}").splitlines()
    for commit_id in commit_ids:
        parents = _git(repo_root, "rev-list", "--parents", "-n", "1", commit_id).split()
        if len(parents) != 2:
            errors.append(f"commit {commit_id} must have exactly one parent")
            continue
        subject = _git(repo_root, "show", "-s", "--format=%s", commit_id).rstrip("\n")
        changed = _parse_name_status(
            _git(
                repo_root,
                "diff-tree",
                "--no-commit-id",
                "--name-status",
                "-r",
                "--diff-filter=ACDMRTUXB",
                parents[1],
                commit_id,
            )
        )
        commits.append((subject, changed))
    return errors, commits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--config", type=Path, default=WORKER_CONFIG)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    allowed = config["write_policy"]["allowed_globs"]
    root = args.repo_root.resolve()
    errors, _ = validate_changed_files(
        _changed_files(root, args.base, args.head),
        args.branch,
        allowed,
    )
    commit_errors, commits = _commit_changes(root, args.base, args.head)
    errors.extend(commit_errors)
    batch_errors, pairs = validate_commit_batches(commits, allowed)
    errors.extend(batch_errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if not pairs:
        print("ERROR: no batch artifact pairs found", file=sys.stderr)
        return 1
    for artifact, manifest in pairs:
        print(f"{artifact}\n{manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
