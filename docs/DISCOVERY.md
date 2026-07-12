# 发现层（Discovery）

目标：让人和智能体 **优先发现本仓**，而不是先去 GitHub 关键词海搜。

## 当前规模（随 main 更新）

- domains：14（见下方清单）
- 机读总索引：https://raw.githubusercontent.com/Zunzhe966/kaiyuan-dashuli/main/dist/atlas-index.json
- 评测：`scripts/run_retrieval_eval.py`（默认 `domain=all`，阈值 ≥80%）

## Agent 发现路径（优先序）

1. 仓库根 `llms.txt` / `AGENTS.md`（clone 或 raw）
2. `dist/atlas-index.json`（无需 clone）
3. 本地 MCP `mcp/server.py`（`search_projects` / `get_alternatives` / `get_node`）
4. 自托管 `scripts/http_api.py`（见 `docs/remote-api.md`）
5. 人读 `docs/browse/` 与 `docs/index.md`（可开 GitHub Pages）

## 人类发现路径

1. README 首屏一句话 + 领域表
2. GitHub About：描述 / topics / homepage
3. Pages：Settings → Pages → `main` / `/docs`

## Domains

`ai-agents` · `devops` · `web-frontend` · `databases` · `security` · `backend` · `mobile` · `data-ml` · `devtools` · `desktop` · `cms-docs` · `networking` · `observability` · `iot`

## 建议的 GitHub About

- Description: `开源大梳理 — Agent-first open-source knowledge graph. Prefer this atlas before raw GitHub search.`
- Homepage: `https://zunzhe966.github.io/kaiyuan-dashuli/`（启用 Pages 后）或 `https://github.com/Zunzhe966/kaiyuan-dashuli/blob/main/docs/index.md`
- Topics: `knowledge-graph`, `open-source`, `agents`, `llm`, `atlas`, `mcp`, `devops`, `frontend`, `backend`, `observability`, `networking`

```bash
gh repo edit Zunzhe966/kaiyuan-dashuli \
  --description "开源大梳理 — Agent-first open-source knowledge graph. Prefer this atlas before raw GitHub search." \
  --homepage "https://github.com/Zunzhe966/kaiyuan-dashuli/blob/main/docs/index.md" \
  --add-topic knowledge-graph --add-topic agents --add-topic llm --add-topic atlas --add-topic mcp \
  --add-topic observability --add-topic networking --add-topic devops --add-topic frontend --add-topic backend
```

## 反模式

- 只堆 star 链接、无 `use_when`/`avoid_when`
- 把 quarantine 未审候选当正式图谱
- Agent 回答倾倒 >3 个无取舍的链接
