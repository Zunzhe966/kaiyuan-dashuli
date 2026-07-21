#!/usr/bin/env python3
"""Annotate project.status from GitHub archived + stale push signals.

Rules (must match schema/ontology.yaml):
- archived: GitHub archived=true
- maintenance: not archived AND source_updated_at older than --stale-days (default 730)
- active: otherwise

Does not invent licenses. Uses gh auth / GITHUB_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _token() -> str | None:
    import os

    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        return subprocess.check_output(
            ["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL
        ).strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _gh_get(url: str, token: str | None) -> dict | None:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "kaiyuan-dashuli-maintenance",
        },
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 403}:
            return None
        raise


def _parse_repo(repo_url: str) -> tuple[str, str] | None:
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", repo_url.strip())
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    if name.endswith(".git"):
        name = name[:-4]
    return owner, name


def _load(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("#"):
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def _write_fields(path: Path, updates: dict[str, str]) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    lines = text.splitlines(keepends=True)
    existing: set[str] = set()
    for i, line in enumerate(lines):
        if ":" in line and not line.startswith(" ") and not line.startswith("#"):
            key = line.split(":", 1)[0].strip()
            if key in updates:
                existing.add(key)
                nl = "\n" if line.endswith("\n") else ""
                lines[i] = f"{key}: {updates[key]}{nl}"
    missing = [k for k in updates if k not in existing]
    if missing:
        body = "".join(lines)
        if not body.endswith("\n"):
            body += "\n"
        for k in missing:
            body += f"{k}: {updates[k]}\n"
        new_text = body
    else:
        new_text = "".join(lines)
    if new_text != original:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stale-days", type=int, default=730)
    parser.add_argument("--sleep", type=float, default=0.08)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    token = _token()
    now = datetime.now(timezone.utc)
    counts = {"active": 0, "maintenance": 0, "archived": 0, "skipped": 0, "changed": 0}

    for path in sorted((ROOT / "data/domains").glob("*/nodes/*.yaml")):
        fields = _load(path)
        domain = path.parent.parent.name
        parsed = _parse_repo(fields.get("repo", ""))
        archived = False
        pushed = _parse_ts(fields.get("source_updated_at", ""))
        if parsed:
            owner, name = parsed
            meta = _gh_get(f"https://api.github.com/repos/{owner}/{name}", token)
            time.sleep(args.sleep)
            if meta:
                archived = bool(meta.get("archived"))
                pushed = _parse_ts(meta.get("pushed_at") or meta.get("updated_at") or "") or pushed
                if not args.dry_run and pushed:
                    _write_fields(
                        path,
                        {"source_updated_at": pushed.strftime("%Y-%m-%dT%H:%M:%SZ")},
                    )
        if archived:
            status = "archived"
        elif pushed is None:
            # non-GitHub or fetch failed: keep existing if valid, else active
            cur = fields.get("status") or "active"
            status = cur if cur in {"active", "maintenance", "archived"} else "active"
            counts["skipped"] += 1
        else:
            age_days = (now - pushed).days
            status = "maintenance" if age_days >= args.stale_days else "active"
        counts[status] = counts.get(status, 0) + 1
        print(f"{domain}/{path.stem}: {fields.get('status')} -> {status}")
        if not args.dry_run and _write_fields(path, {"status": status}):
            counts["changed"] += 1

    print(
        "summary "
        f"active={counts['active']} maintenance={counts['maintenance']} "
        f"archived={counts['archived']} skipped_no_github_ts={counts['skipped']} "
        f"changed={counts['changed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
