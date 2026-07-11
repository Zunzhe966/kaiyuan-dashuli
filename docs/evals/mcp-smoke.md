# MCP smoke

- tools: get_alternatives, get_node, search_projects

## search_projects
```json
{
  "results": [
    {
      "id": "open-webui",
      "name": "Open WebUI",
      "repo": "https://github.com/open-webui/open-webui",
      "summary": "自托管的 ChatGPT 风格 Web UI，常配 Ollama。",
      "use_when": "给本地/私有模型一个好用聊天界面",
      "avoid_when": "只要 API 不要前端",
      "score": 5.0
    },
    {
      "id": "ollama",
      "name": "Ollama",
      "repo": "https://github.com/ollama/ollama",
      "summary": "本地一键跑开源大模型的运行时与模型分发。",
      "use_when": "本地/内网推理、快速试用开源模型",
      "avoid_when": "需要大规模分布式推理集群（应看 vLLM 等）",
      "score": 5.0
    },
    {
      "id": "llama-cpp",
      "name": "llama.cpp",
      "repo": "https://github.com/ggml-org/llama.cpp",
      "summary": "C/C++ 本地 LLM 推理，GGUF 生态核心。",
      "use_when": "CPU/消费级 GPU 本地跑量化模型、嵌入式部署",
      "avoid_when": "需要多租户高并发 OpenAI 兼容服务集群",
      "score": 5.0
    }
  ]
}
```

## get_node(ollama) edges=5
