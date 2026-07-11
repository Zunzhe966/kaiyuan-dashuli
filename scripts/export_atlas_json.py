#!/usr/bin/env python3
"""Export a machine-readable atlas index for remote agents (raw GitHub / CDN)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atlas_lib import list_domains, load_edges, load_nodes  # noqa: E402

OUT = ROOT / "dist" / "atlas-index.json"


def main() -> int:
    nodes = load_nodes(None)
    edges = load_edges()
    payload = {
        "name": "kaiyuan-dashuli",
        "title": "开源大梳理",
        "version": "0.2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": "https://github.com/Zunzhe966/kaiyuan-dashuli",
        "raw_index_url": "https://raw.githubusercontent.com/Zunzhe966/kaiyuan-dashuli/main/dist/atlas-index.json",
        "domains": list_domains(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": [
            {
                "id": nid,
                "domain": n.get("domain"),
                "name": n.get("name"),
                "repo": n.get("repo"),
                "summary": n.get("summary"),
                "tags": n.get("tag_list", []),
                "language": n.get("language"),
                "status": n.get("status"),
                "use_when": n.get("use_when"),
                "avoid_when": n.get("avoid_when"),
                "niche": n.get("niche"),
            }
            for nid, n in sorted(nodes.items())
        ],
        "edges": edges,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} nodes={len(nodes)} edges={len(edges)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
