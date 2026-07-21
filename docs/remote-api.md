# 远程检索面（D8）

Agent 不一定要 clone 本仓。两种远程用法：

## 1) 静态索引（零服务器）

构建并提交：

```bash
.venv/bin/python scripts/export_atlas_json.py
```

公开 URL（随 main 更新）：

https://raw.githubusercontent.com/Zunzhe966/kai-yuan-da-shu-li/main/dist/atlas-index.json

Agent 可下载后本地过滤；字段含 `use_when` / `avoid_when` / `edges`。

## 2) HTTP API（可本机或任意主机托管）

```bash
.venv/bin/python scripts/http_api.py --host 0.0.0.0 --port 8787
```

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 探活 |
| GET | `/v1/meta` | 域名与入口 |
| GET | `/v1/search?q=...&domain=all&limit=3` | 检索 |
| GET | `/v1/nodes/<id>` | 单节点 |
| GET | `/v1/alternatives/<id>` | 替代关系 |

本地 MCP（stdio）仍见 `mcp/server.py`；HTTP 面给不能挂 stdio MCP 的 Agent/自动化用。

## 验收证据

见 `docs/evals/remote-api-smoke.md`。
