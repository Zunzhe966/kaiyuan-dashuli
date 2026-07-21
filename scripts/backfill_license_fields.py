#!/usr/bin/env python3
"""Backfill license / verified_at / source_updated_at / verification_status on node YAML.

Uses GitHub API (gh auth or GITHUB_TOKEN). Does not invent licenses:
1. repo.license.spdx_id when not NOASSERTION/OTHER
2. decode /license (or LICENSE*) body and match known SPDX / LicenseRef patterns
3. optional curated overrides (explicit SPDX only)

Unknown stays empty with verification_status=needs_review and quality_notes reason.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPDX_HINTS = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "gpl-3.0": "GPL-3.0",
    "gpl-2.0": "GPL-2.0",
    "agpl-3.0": "AGPL-3.0",
    "lgpl-3.0": "LGPL-3.0",
    "mpl-2.0": "MPL-2.0",
    "isc": "ISC",
    "unlicense": "Unlicense",
    "cc0-1.0": "CC0-1.0",
    "0bsd": "0BSD",
    "bsl-1.0": "BSL-1.0",
    "epl-2.0": "EPL-2.0",
    "eupl-1.2": "EUPL-1.2",
    "busl-1.1": "BUSL-1.1",
    "sspl-1.0": "SSPL-1.0",
}

BODY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Apache License[, ]+Version 2\.0|Licensed under the Apache License,? Version 2\.0", re.I), "Apache-2.0"),
    (re.compile(r"\bMIT License\b|Permission is hereby granted, free of charge, to any person obtaining a copy of this software", re.I), "MIT"),
    (re.compile(r"GNU AFFERO GENERAL PUBLIC LICENSE\s+Version 3", re.I), "AGPL-3.0"),
    (re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3", re.I), "LGPL-3.0"),
    (re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 3", re.I), "GPL-3.0"),
    (re.compile(r"GNU GENERAL PUBLIC LICENSE\s+Version 2", re.I), "GPL-2.0"),
    (re.compile(r"Mozilla Public License[, ]+Version? ?2\.0|\bMPL(?:-| )?2\.0\b|LICENSE-MPL", re.I), "MPL-2.0"),
    (re.compile(r"\bBSD 3-Clause\b|Neither the name of (?:the )?(?:copyright holder|author)", re.I), "BSD-3-Clause"),
    (re.compile(r"\bBSD 2-Clause\b|THE SOFTWARE IS PROVIDED \"AS IS\" AND THE AUTHOR DISCLAIMS ALL WARRANTIES", re.I), "BSD-2-Clause"),
    (re.compile(r"\bISC License\b", re.I), "ISC"),
    (re.compile(r"Creative Commons Zero|CC0 1\.0", re.I), "CC0-1.0"),
    (re.compile(r"Boost Software License", re.I), "BSL-1.0"),
    (re.compile(r"Eclipse Public License - v 2\.0", re.I), "EPL-2.0"),
    (re.compile(r"European Union Public Licence|EUPL", re.I), "EUPL-1.2"),
    (re.compile(r"Business Source License 1\.1|\bBUSL-1\.1\b", re.I), "BUSL-1.1"),
    (re.compile(r"Server Side Public License|\bSSPL-1\.0\b", re.I), "SSPL-1.0"),
]

CUSTOM_MARKERS: list[tuple[str, str]] = [
    ("Sustainable Use License", "LicenseRef-SustainableUse"),
    ("Elastic License 2.0", "LicenseRef-Elastic-2.0"),
    ("Elastic License", "LicenseRef-Elastic"),
    ("PolyForm Shield", "LicenseRef-PolyForm-Shield"),
    ("PolyForm Noncommercial", "LicenseRef-PolyForm-Noncommercial"),
    ("Commons Clause", "LicenseRef-CommonsClause"),
    ("CockroachDB Software License", "LicenseRef-CockroachDB-CSL"),
    ("SCYLLADB SOFTWARE LICENSE AGREEMENT", "LicenseRef-ScyllaDB-Source-Available"),
    ("Spine Runtimes License", "LicenseRef-SpineRuntimes"),
    ("ImageMagick License", "ImageMagick"),
    ("PostgreSQL Database Management System", "PostgreSQL"),
    ("SQLite Is Public Domain", "blessing"),
    ("wxWindows Library Licence", "LicenceRef-wxWindows"),
    ("END-USER LICENSE AGREEMENT FOR ASEPRITE", "LicenseRef-Aseprite-EULA"),
    ("Creative Commons Attribution 4.0", "CC-BY-4.0"),
    ("zlib/libpng license", "Zlib"),
    ("zlib license", "Zlib"),
    ("GNU LIBRARY GENERAL PUBLIC LICENSE", "LGPL-2.0-only"),
    ("GNU LESSER GENERAL PUBLIC LICENSE Version 2.1", "LGPL-2.1-only"),
]

# Curated overrides: only for repos where GitHub is silent but license is publicly documented.
# Keys: "owner/repo" → SPDX expression. Dual OSS+EE: record community/core SPDX.
CURATED: dict[str, str] = {
    "laravel/laravel": "MIT",
    "paritytech/polkadot-sdk": "GPL-3.0-only WITH Classpath-exception-2.0",
    "Zunzhe966/kai-yuan-da-shu-li": "CC-BY-4.0",
    "FlowiseAI/Flowise": "Apache-2.0",
    "langfuse/langfuse": "MIT",
    "SigNoz/signoz": "MIT",
    "goauthentik/authentik": "MIT",
    "ipfs/kubo": "MIT OR Apache-2.0",
    "postgres/postgres": "PostgreSQL",
    "sqlite/sqlite": "blessing",
    "GNOME/gtk": "LGPL-2.0-only",
    "bulletphysics/bullet3": "Zlib",
    "jarikomppa/soloud": "Zlib",
    "EsotericSoftware/spine-runtimes": "LicenseRef-SpineRuntimes",
    "OSGeo/grass": "GPL-2.0-or-later",
    "MapServer/MapServer": "MIT",
    "OSGeo/PROJ": "MIT",
    "blender/blender": "GPL-2.0-or-later",
    "GStreamer/gstreamer": "LGPL-2.1-only",
    "ImageMagick/ImageMagick": "ImageMagick",
    "shorebirdtech/shorebird": "Apache-2.0",
    "haproxy/haproxy": "GPL-2.0-only",
    "cockroachdb/cockroach": "LicenseRef-CockroachDB-CSL",
    "scylladb/scylladb": "LicenseRef-ScyllaDB-Source-Available",
    "JetBrains/kotlin": "Apache-2.0",
    "wxWidgets/wxWidgets": "LicenceRef-wxWindows",
    "aseprite/aseprite": "LicenseRef-Aseprite-EULA",
    "NomicFoundation/hardhat": "MIT",
    "matplotlib/matplotlib": "LicenseRef-matplotlib",
    "qt/qtbase": "LGPL-3.0-only",
    "arduino/ArduinoCore-avr": "LGPL-2.1-or-later",
    "android/kotlin-guides": "Apache-2.0",
}


def _token() -> str | None:
    import os

    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        out = subprocess.check_output(
            ["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        return out or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _gh_get(url: str, token: str | None) -> dict | list | None:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "kaiyuan-dashuli-backfill",
        },
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
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


def _normalize_license(raw: str | None) -> str:
    if not raw:
        return ""
    key = raw.strip().lower()
    if key in {"noassertion", "other", "none"}:
        return ""
    return SPDX_HINTS.get(key, raw.strip())


def _decode_content(payload: dict) -> str:
    raw = payload.get("content") or ""
    if not raw:
        return ""
    return base64.b64decode(raw).decode("utf-8", "replace")


def _fetch_license_text(owner: str, name: str, token: str | None) -> str:
    data = _gh_get(f"https://api.github.com/repos/{owner}/{name}/license", token)
    if isinstance(data, dict) and data.get("content"):
        return _decode_content(data)
    for path in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "LICENSE.rst", "LICENCE"):
        item = _gh_get(f"https://api.github.com/repos/{owner}/{name}/contents/{path}", token)
        if isinstance(item, dict) and item.get("content"):
            return _decode_content(item)
    return ""


def _detect_from_body(text: str) -> tuple[str, str]:
    if not text.strip():
        return "", "empty-body"
    lower = text.lower()
    for marker, spdx in CUSTOM_MARKERS:
        if marker.lower() in lower:
            return spdx, "custom-marker"
    # Common OSS-core + EE carve-out README licenses
    m_core = re.search(
        r'available under the ["\']?(Apache 2\.0|MIT Expat|MIT)["\']? license',
        text,
        re.I,
    )
    if m_core:
        raw = m_core.group(1).lower()
        if "apache" in raw:
            return "Apache-2.0", "oss-core-carveout"
        return "MIT", "oss-core-carveout"
    m = re.search(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+\-]+(?:\s+(?:OR|AND|WITH)\s+[A-Za-z0-9.+\-]+)*)", text)
    if m:
        return m.group(1).strip(), "spdx-id-line"
    hits: list[str] = []
    for pat, spdx in BODY_PATTERNS:
        if pat.search(text):
            if spdx not in hits:
                hits.append(spdx)
    if len(hits) == 1:
        return hits[0], "body"
    if len(hits) > 1:
        # Prefer stronger / more specific when MIT false-positive with BSD redistribution.
        if "MIT" in hits and any(x.startswith("BSD") for x in hits):
            hits = [x for x in hits if x != "MIT"]
            if len(hits) == 1:
                return hits[0], "body"
        return " OR ".join(hits), "multi"
    # BSD-ish without explicit clause name
    if re.search(r"Redistribution and use in source and binary forms", text, re.I):
        if re.search(r"Neither the name", text, re.I):
            return "BSD-3-Clause", "bsd-heuristic"
        return "BSD-2-Clause", "bsd-heuristic"
    if re.search(r"covered by GPL version 2|Historically, haproxy has been covered by GPL", text, re.I):
        return "GPL-2.0-only", "haproxy-note"
    if re.search(r"under the terms of the GNU General Public License", text, re.I):
        if re.search(r"version 3", text, re.I):
            return "GPL-3.0-or-later", "gpl-statement"
        return "GPL-2.0-or-later", "gpl-statement"
    return "", "unrecognized"


def _resolve_license(owner: str, name: str, meta: dict, token: str | None) -> tuple[str, str]:
    curated = CURATED.get(f"{owner}/{name}")
    if curated:
        return curated, "curated"
    lic_obj = meta.get("license") or {}
    spdx = _normalize_license(lic_obj.get("spdx_id") if isinstance(lic_obj, dict) else None)
    if spdx:
        return spdx, "repo-api"
    text = _fetch_license_text(owner, name, token)
    detected, how = _detect_from_body(text)
    if detected:
        return detected, how
    return "", how if text else "no-license-file"


def _load_simple_yaml(path: Path) -> dict[str, str]:
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


def _iter_node_paths(domains: list[str] | None, only_empty: bool) -> list[Path]:
    roots = (
        [ROOT / "data/domains" / d / "nodes" for d in domains]
        if domains
        else sorted((ROOT / "data/domains").glob("*/nodes"))
    )
    paths: list[Path] = []
    for nodes_dir in roots:
        if not nodes_dir.is_dir():
            continue
        for path in sorted(nodes_dir.glob("*.yaml")):
            fields = _load_simple_yaml(path)
            if only_empty and fields.get("license"):
                continue
            paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domains", nargs="+", default=None)
    parser.add_argument("--only-empty", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.12)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--residual-csv",
        type=Path,
        default=ROOT / "var/feedback/license-residual.csv",
    )
    args = parser.parse_args()
    token = _token()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = skipped = unknown = filled = 0
    residual_rows: list[dict[str, str]] = []

    for path in _iter_node_paths(args.domains, args.only_empty):
        domain = path.parent.parent.name
        fields = _load_simple_yaml(path)
        if (
            not args.only_empty
            and fields.get("license")
            and fields.get("verified_at")
            and fields.get("source_updated_at")
        ):
            skipped += 1
            continue
        parsed = _parse_repo(fields.get("repo", ""))
        if not parsed:
            unknown += 1
            residual_rows.append(
                {
                    "domain": domain,
                    "id": path.stem,
                    "repo": fields.get("repo", ""),
                    "license": "",
                    "reason": "no-github-repo",
                }
            )
            continue
        owner, name = parsed
        meta = _gh_get(f"https://api.github.com/repos/{owner}/{name}", token)
        time.sleep(args.sleep)
        if not isinstance(meta, dict):
            unknown += 1
            residual_rows.append(
                {
                    "domain": domain,
                    "id": path.stem,
                    "repo": f"{owner}/{name}",
                    "license": "",
                    "reason": "repo-fetch-failed",
                }
            )
            continue
        spdx, how = _resolve_license(owner, name, meta, token)
        time.sleep(args.sleep)
        pushed = meta.get("pushed_at") or meta.get("updated_at") or ""
        if spdx:
            status = "verified"
            filled += 1
            notes = fields.get("quality_notes", "")
            # strip prior license-review notes if any
            if notes.startswith("license-review:"):
                notes = ""
            updates = {
                "license": spdx,
                "source_updated_at": pushed,
                "verified_at": now,
                "verification_status": status,
            }
            if notes:
                updates["quality_notes"] = notes
        else:
            status = "needs_review"
            reason = f"license-review:{how}"
            residual_rows.append(
                {
                    "domain": domain,
                    "id": path.stem,
                    "repo": f"{owner}/{name}",
                    "license": "",
                    "reason": how,
                }
            )
            updates = {
                "license": "",
                "source_updated_at": pushed,
                "verified_at": now,
                "verification_status": status,
                "quality_notes": reason,
            }
        print(f"{domain}/{path.stem}: license={spdx or 'UNKNOWN'} via={how} status={status}")
        if not args.dry_run and _write_fields(path, updates):
            changed += 1

    args.residual_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.residual_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["domain", "id", "repo", "license", "reason"]
        )
        writer.writeheader()
        writer.writerows(residual_rows)
    print(
        f"changed={changed} skipped={skipped} unknown={unknown} "
        f"filled={filled} residual={len(residual_rows)} csv={args.residual_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
