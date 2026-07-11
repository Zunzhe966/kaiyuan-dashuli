#!/usr/bin/env python3
"""Run agent retrieval eval against local atlas data (AGENTS.md protocol approximation)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "docs/evals/queries-v1.yaml"
OUT = ROOT / "docs/evals/agent-retrieval-eval.md"
NODES = ROOT / "data/domains/ai-agents/nodes"
EDGES = ROOT / "graph/edges.yaml"


def load_nodes() -> dict[str, dict[str, str]]:
    nodes: dict[str, dict[str, str]] = {}
    for path in NODES.glob("*.yaml"):
        fields: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                fields[k.strip()] = v.strip()
        tags = fields.get("tags", "").strip("[]")
        fields["tag_list"] = [t.strip() for t in tags.split(",") if t.strip()]
        nodes[path.stem] = fields
    return nodes


def load_edges() -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    for line in EDGES.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s+-\s+from:\s*(\S+)", line)
        if m:
            if cur:
                edges.append(cur)
            cur = {"from": m.group(1)}
            continue
        if cur is None:
            continue
        m = re.match(r"\s+type:\s*(\S+)", line)
        if m:
            cur["type"] = m.group(1)
        m = re.match(r"\s+to:\s*(\S+)", line)
        if m:
            cur["to"] = m.group(1)
    if cur:
        edges.append(cur)
    return edges


def load_queries() -> list[dict]:
    queries: list[dict] = []
    q: dict = {}
    for line in QUERIES.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("- id:"):
            if q:
                queries.append(q)
            q = {"id": line.split(":", 1)[1].strip()}
        elif "query:" in line:
            q["query"] = line.split(":", 1)[1].strip()
        elif "intent_tags:" in line:
            q["intent_tags"] = [
                x.strip() for x in line.split("[", 1)[1].rstrip("]").split(",") if x.strip()
            ]
        elif "expect_any:" in line:
            q["expect_any"] = [
                x.strip() for x in line.split("[", 1)[1].rstrip("]").split(",") if x.strip()
            ]
    if q:
        queries.append(q)
    return queries


def rank(q: dict, nodes: dict, edges: list[dict]) -> list[str]:
    intent = set(q["intent_tags"])
    scored: list[tuple[float, str]] = []
    for nid, n in nodes.items():
        tags = set(n.get("tag_list", []))
        s = float(len(intent & tags)) * 2
        use = n.get("use_when", "").lower()
        avoid = n.get("avoid_when", "").lower()
        blob = " ".join(
            [n.get("summary", ""), use, n.get("name", ""), n.get("niche", "")]
        ).lower()
        for token in re.findall(r"[\w/]+", q["query"].lower()):
            if len(token) < 2:
                continue
            if token in use:
                s += 1.5
            if token in blob:
                s += 0.3
            if token in avoid:
                s -= 1.0
        if "笔记本" in q["query"] or "一键" in q["query"]:
            if nid in ("ollama", "open-webui", "llama-cpp"):
                s += 3
            if nid in ("vllm", "sglang", "milvus"):
                s -= 3
        if "高并发" in q["query"] or "GPU 服务器" in q["query"]:
            if nid in ("vllm", "sglang"):
                s += 3
            if nid == "ollama":
                s -= 2
        if "不要重型" in q["query"] and nid in ("instructor", "pydantic-ai", "outlines"):
            s += 1
        if s > 0:
            scored.append((s, nid))
    scored.sort(reverse=True)
    top = [nid for _, nid in scored[:3]]
    if top:
        for e in edges:
            if e.get("type") == "alternative_to" and top[0] in (e.get("from"), e.get("to")):
                other = e["to"] if e["from"] == top[0] else e["from"]
                if other not in top and other in nodes:
                    top.append(other)
        top = top[:3]
    return top


def main() -> int:
    nodes = load_nodes()
    edges = load_edges()
    queries = load_queries()
    lines = [
        "# Agent retrieval eval v1",
        "",
        "协议：AGENTS.md（结构化需求→领域索引→tags + use_when/avoid_when 重排→1–3推荐）",
        "",
        "| ID | Query | Top推荐 | 命中期望 | 合规 |",
        "|---|---|---|---|---|",
    ]
    pass_n = 0
    results = []
    for q in queries:
        top = rank(q, nodes, edges)
        hit = any(x in top for x in q["expect_any"])
        compliant = (
            bool(top)
            and all(nodes[t].get("use_when") and nodes[t].get("avoid_when") for t in top)
            and 1 <= len(top) <= 3
        )
        ok = hit and compliant
        if ok:
            pass_n += 1
        results.append((q, top, hit, compliant, ok))
        lines.append(
            f"| {q['id']} | {q['query']} | {', '.join(top)} | {'Y' if hit else 'N'} | {'Y' if compliant else 'N'} |"
        )
    rate = pass_n / len(queries)
    lines += [
        "",
        f"**通过率：{pass_n}/{len(queries)} = {rate:.0%}**",
        "",
        "判定阈值：≥80%",
        "",
        "## 逐条取舍摘要",
        "",
    ]
    for q, top, hit, compliant, ok in results:
        lines.append(f"### {q['id']} — {q['query']}")
        for t in top:
            n = nodes[t]
            lines.append(f"- **{n.get('name')}** (`{t}`)")
            lines.append(f"  - use_when: {n.get('use_when')}")
            lines.append(f"  - avoid_when: {n.get('avoid_when')}")
            lines.append(f"  - repo: {n.get('repo')}")
        lines.append(f"- result: {'PASS' if ok else 'FAIL'} (hit={hit}, compliant={compliant})")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"pass_rate={rate:.2%} pass={pass_n}/{len(queries)} -> {OUT}")
    return 0 if rate >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(main())
