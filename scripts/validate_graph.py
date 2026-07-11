#!/usr/bin/env python3
"""Validate atlas graph: required fields, index ids, edge endpoints."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "data/domains/ai-agents"
NODES = DOMAIN / "nodes"
INDEX = DOMAIN / "_index.yaml"
EDGES = ROOT / "graph/edges.yaml"
REQUIRED = ("id", "name", "repo", "summary", "tags", "status", "use_when", "avoid_when")


def parse_simple_yaml_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fields[k.strip()] = v.strip()
    return fields


def main() -> int:
    errors: list[str] = []
    node_files = sorted(NODES.glob("*.yaml"))
    ids: set[str] = set()
    for path in node_files:
        text = path.read_text(encoding="utf-8")
        fields = parse_simple_yaml_fields(text)
        nid = fields.get("id", "")
        if nid != path.stem:
            errors.append(f"{path.name}: id '{nid}' != filename stem '{path.stem}'")
        for key in REQUIRED:
            if key not in fields or not fields[key]:
                errors.append(f"{path.name}: missing required field '{key}'")
        if "repo" in fields and not fields["repo"].startswith("http"):
            errors.append(f"{path.name}: repo must be http(s) URL")
        ids.add(path.stem)

    index_text = INDEX.read_text(encoding="utf-8")
    index_ids = set(re.findall(r"node_ids:\s*\[([^\]]+)\]", index_text))
    flat: set[str] = set()
    for block in re.findall(r"node_ids:\s*\[([^\]]+)\]", index_text):
        for part in block.split(","):
            part = part.strip()
            if part:
                flat.add(part)
    for i in flat:
        if i not in ids:
            errors.append(f"_index.yaml references missing node '{i}'")
    for i in ids:
        if i not in flat:
            errors.append(f"node '{i}' exists but not listed in _index.yaml")

    edges_text = EDGES.read_text(encoding="utf-8")
    edge_ids = set(re.findall(r"^\s+(?:from|to):\s*(\S+)", edges_text, re.M))
    for e in edge_ids:
        if e not in ids:
            errors.append(f"edges.yaml endpoint missing node '{e}'")
    edge_count = len(re.findall(r"^\s+-\s+from:", edges_text, re.M))

    print(f"nodes={len(node_files)} edges={edge_count} index_ids={len(flat)}")
    if errors:
        print(f"ERRORS={len(errors)}")
        for e in errors:
            print(f"- {e}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
