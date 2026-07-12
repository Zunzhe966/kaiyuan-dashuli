# MCP smoke (atlas_lib equivalent)

工具面与 `mcp/server.py` 一致：`search_projects` / `get_alternatives` / `get_node`。

复测范围：全域（含 gis/gamedev/media/iot）。

## search_projects · GIS
```json
[
  {
    "id": "nomad",
    "domain": "devops",
    "name": "Nomad",
    "repo": "https://github.com/hashicorp/nomad",
    "summary": "HashiCorp 通用工作负载调度器，比 K8s 更轻。",
    "use_when": "要调度容器/非容器任务又不想上满血 K8s",
    "avoid_when": "团队标准已是 Kubernetes 且生态绑定深",
    "score": 3.0
  },
  {
    "id": "leaflet",
    "domain": "gis",
    "name": "Leaflet",
    "repo": "https://github.com/Leaflet/Leaflet",
    "summary": "轻量移动友好的网页地图库。",
    "use_when": "网页嵌入轻量交互地图",
    "avoid_when": "要复杂 3D/海量矢量瓦片引擎",
    "score": 1.8
  },
  {
    "id": "kubernetes",
    "domain": "devops",
    "name": "Kubernetes",
    "repo": "https://github.com/kubernetes/kubernetes",
    "summary": "容器编排标准，调度多机工作负载。",
    "use_when": "多机/多服务需要编排、自愈、滚动发布",
    "avoid_when": "单机小服务，K8s 运维成本过高",
    "score": 0.0
  }
]
```

## search_projects · gamedev
```json
[
  {
    "id": "monogame",
    "domain": "gamedev",
    "name": "MonoGame",
    "repo": "https://github.com/MonoGame/MonoGame",
    "summary": "跨平台游戏框架（XNA 精神后继）。",
    "use_when": ".NET 团队要跨平台 2D/3D 框架",
    "avoid_when": "非 C# 栈",
    "score": 6.6
  },
  {
    "id": "godot",
    "domain": "gamedev",
    "name": "Godot Engine",
    "repo": "https://github.com/godotengine/godot",
    "summary": "功能完整的开源游戏引擎。",
    "use_when": "要开源、轻量、一体化的 2D/3D 引擎",
    "avoid_when": "团队已深度绑定商业引擎管线",
    "score": 6.6
  },
  {
    "id": "raylib",
    "domain": "gamedev",
    "name": "raylib",
    "repo": "https://github.com/raysan5/raylib",
    "summary": "简单易学的游戏编程库。",
    "use_when": "教学或快速做 2D/简单 3D 原型",
    "avoid_when": "要完整场景编辑器与资源管线",
    "score": 3.6
  }
]
```

## get_alternatives(godot)
```json
[
  {
    "id": "bevy",
    "domain": "gamedev",
    "name": "Bevy",
    "repo": "https://github.com/bevyengine/bevy",
    "summary": "数据驱动的 Rust 游戏引擎。",
    "use_when": "要用 Rust ECS 做游戏/交互应用",
    "avoid_when": "要开箱即用的可视化编辑器为主",
    "edge_type": "alternative_to",
    "note": "一体化开源引擎 vs Rust ECS 引擎"
  },
  {
    "id": "phaser",
    "domain": "gamedev",
    "name": "Phaser",
    "repo": "https://github.com/phaserjs/phaser",
    "summary": "快速的 HTML5 游戏框架。",
    "use_when": "要浏览器 2D 游戏",
    "avoid_when": "要原生高性能 3D",
    "edge_type": "alternative_to",
    "note": "Web 2D vs 通用引擎导出"
  },
  {
    "id": "monogame",
    "domain": "gamedev",
    "name": "MonoGame",
    "repo": "https://github.com/MonoGame/MonoGame",
    "summary": "跨平台游戏框架（XNA 精神后继）。",
    "use_when": ".NET 团队要跨平台 2D/3D 框架",
    "avoid_when": "非 C# 栈",
    "edge_type": "alternative_to",
    "note": ".NET 框架 vs Godot"
  },
  {
    "id": "openmw",
    "domain": "gamedev",
    "name": "OpenMW",
    "repo": "https://github.com/OpenMW/openmw",
    "summary": "《上古卷轴 III》引擎重实现。",
    "use_when": "研究开放世界 RPG 引擎或玩 OpenMW",
    "avoid_when": "要通用新项目引擎",
    "edge_type": "alternative_to",
    "note": "特定游戏重实现 vs 通用引擎"
  }
]
```

## get_node(postgis) edges=3
## get_node(kaiyuan-dashuli) present=True

判定：PASS（多域召回 + 替代边 + 作者项目节点仍可取）。
