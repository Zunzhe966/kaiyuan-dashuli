# ai-agents 子类 taxonomy（D2 / S2.1）

> 服务领域：`data/domains/ai-agents/`  
> 与 `schema/ontology.yaml` 的 tags 对齐；节点挂入 `_index.yaml` 对应 category。

| id | 标题 | 收录什么 | 典型 tags |
|---|---|---|---|
| agent-frameworks | Agent / LLM 应用框架 | 编排、工具调用、链/图工作流 | agent-framework, orchestration |
| multi-agent | 多 Agent 协作 | 多角色、对话协作、群组调度 | multi-agent |
| rag-data | RAG / 数据框架 | 索引、连接器、文档问答流水线 | rag |
| vector-db | 向量库 / 检索后端 | 嵌入存储与相似度检索 | vector-db, rag |
| mcp-tooling | MCP / 工具协议 | MCP server、协议实现、工具网关 | mcp |
| local-llm | 本地 / 推理运行时 | 本机或自托管模型服务 | local-llm, llm-api |
| eval-quality | 评测与质量 | benchmark、评测框架、回归集 | eval |
| observability | 观测与追踪 | tracing、prompt 日志、成本监控 | observability |
| prompt-ops | 提示词与护栏 | prompt 管理、guardrails、结构化输出 | prompt |
| fine-tuning | 微调 / 训练辅助 | SFT、偏好对齐、训练工具链 | fine-tuning |
| datasets | 数据集 | 指令集、评测集、语料 | dataset |
| agent-ui | Agent / Chat UI | 对话前端、控制台、playground | ui |

**质检门槛（写入节点时）：** 必须有 `use_when` + `avoid_when`；禁止只抄 star 数当理由。
