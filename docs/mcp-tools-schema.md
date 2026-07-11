# MCP 工具契约（D4 / S4.1）

本图谱的 Agent 检索层先以 **本地 MCP** 提供三个只读工具。数据源：仓库内 YAML（不另建库）。

## Tools

### 1. `search_projects`

按自然语言/标签检索项目节点。

**Input**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| query | string | 是 | 用户需求描述 |
| tags | string[] | 否 | 额外强制标签过滤 |
| domain | string | 否 | 默认 `ai-agents` |
| limit | number | 否 | 默认 3，最大 5 |

**Output**

```json
{
  "results": [
    {
      "id": "ollama",
      "name": "Ollama",
      "repo": "https://github.com/ollama/ollama",
      "summary": "...",
      "use_when": "...",
      "avoid_when": "...",
      "score": 1.23
    }
  ]
}
```

### 2. `get_alternatives`

给定节点，返回 `alternative_to` / `supersedes` 邻居。

**Input**

| 字段 | 类型 | 必填 |
|---|---|---|
| id | string | 是 |
| limit | number | 否，默认 5 |

**Output**：节点摘要列表 + `edge_type` + `note`。

### 3. `get_node`

按 id 取完整节点 + 相关边。

**Input**：`id`（必填）  
**Output**：node YAML 字段对象 + `edges: [{type, direction, other_id, note}]`

## 非目标（本步不做）

- 写操作 / 自动灌库
- 远程托管 API（可后置；契约保持兼容）
- 认证付费墙
