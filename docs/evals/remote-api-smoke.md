# Remote API smoke (D8)

Date: 2026-07-12

## Static index

- file: `dist/atlas-index.json`
- counts: nodes=96 edges=88 domains=3
- public URL (after push): https://raw.githubusercontent.com/Zunzhe966/kaiyuan-dashuli/main/dist/atlas-index.json

## HTTP API (`scripts/http_api.py`)

Observed earlier in-session:

| Call | Result |
|---|---|
| `GET /health` | ok |
| `GET /v1/meta` | domains = ai-agents, devops, web-frontend |
| `GET /v1/search?q=本地笔记本跑模型&domain=ai-agents&limit=2` | open-webui, ollama |
| `GET /v1/nodes/nextjs` | id=nextjs |
| `GET /v1/alternatives/react` | vue, svelte |

PASS
