# GPT-5.6 审核与发布职责

这不是 DeepSeek 数据工提示词。它固定高级审核与生产发布边界。

## 1. 负责事项

GPT-5.6 审核发布任务负责：

1. 制定并维护 V2 Schema、受控分类词表、验证器、迁移器和查询语义。
2. 用户指定接管时记录持续积累 PR 的冻结提交 SHA，对上次审核点之后、该 SHA 之前的全部 DeepSeek 批次执行集中审核；不要求每批等待人工审核。
3. 通过风险分层抽样评估普通批次；发现系统性错误时退回整个批次并修正规则，不逐条掩盖。
4. 决定记录保持 discovery/quarantine、提升到精选图谱、合并重复项或排除。
5. 接受通过的 PR；试点批次可合并，规模化批次由摄取流程写入对象存储并只在 `main` 保存清单、摘要与提升后的精选数据，避免 Git 仓库无限膨胀。
6. 修复并维护 GitHub `main → verify → pages-deploy → Cloudflare Pages` 的稳定连通。
7. 用提交 SHA、目录摘要、Schema 版本、节点数和边数验证线上站确实来自当前 `main`。
8. 维护私有总账中的域名、账户、广告、收款、税务和发布证据；不公开敏感信息。

当前发布事实以 [`cloudflare-pages-connection.md`](./cloudflare-pages-connection.md) 的带日期状态为准；历史“已连接”描述不能覆盖最新 Actions 日志。2026-07-22 的实际阻塞是 Cloudflare Token 认证失败，不是 GitHub 触发或本地构建失败。

## 2. 不交给 DeepSeek 的工作

- 修改 `schema/`、`scripts/`、`tests/`、`.github/workflows/`、`site_src/`、`dist/` 或生产配置。
- 裁决许可证冲突、分类词表冲突和 Schema 变更。
- 合并 PR、直接写 `main`、操作 Cloudflare、轮换 Token 或验证生产部署。
- 购买域名、广告开户、银行税务或任何需要外部主体责任的动作。

## 3. 数据批次审核门槛

每个冻结提交 SHA 的审核窗口执行：

1. 100% 格式、枚举、ID、证据闭合、manifest 和秘密扫描；受信任 `pull_request_target` 门禁必须从 base 分支加载合同，首次批次及每次唯一直接后继批次各在线重取一次 GitHub 枚举页，所有历史批次每次离线重放，不能执行 PR 自带验证器。
2. 100% 复核 `conflicting`、许可证版本变化、open-core/source-available、fork/镜像/改名和安全高风险记录。
3. 前三批人工/高级模型抽检至少 20% 且不少于 5 条；连续三批关键字段准确率达到 99% 后，可降至 5% 且不少于 5 条。
4. 抽检出现身份重复、伪造证据、许可证误判或非 unknown 无证据时，整批退回并扩大下一批抽检，不只修样本。
5. 只有校验、抽检和冲突处置全部通过才接受；是否合并原始批次或仅摄取并保存清单，按当前存储阶段决定。正式提升流程另行决定哪些数据进入网站。

审核开始时记录 `base_main_sha`、`last_reviewed_sha` 和 `frozen_head_sha`，并确认 DeepSeek停止向该 PR继续推送。审核期间只判断冻结范围；通过则合并并关闭本轮持续积累 PR，退回则关闭或建立明确的替换分支。下一轮 DeepSeek必须从审核后的新 `origin/main`启动。未审核数据不得进入正式图谱或网站。

## 4. GitHub 与网站连通

正常生产链路固定为：

```text
DeepSeek 持续积累 PR
→ 用户指定时按冻结提交 SHA 集中审核
→ 试点进入 quarantine；规模化批次进入对象存储并在 GitHub 留清单
→ 精选提升数据进入 GitHub 正式源
→ 受保护 main
→ GitHub Actions verify
→ pages-deploy 重建 build/site
→ Wrangler 上传 Cloudflare Pages
→ 线上 meta/提交/摘要/关键查询验收
```

Cloudflare Pages 不直接接收 DeepSeek 文件，也不与 GitHub 双向同步。只有经过集中审核、进入正式事实源且被构建器选择发布的数据才会出现在网站。持续积累 PR中未审核、只进入 discovery/quarantine 或验证失败的数据不应改变网站。全球发现层规模化后由动态查询 API 读取对象存储索引；精选静态页面继续由 GitHub `main` 构建。

## 5. 当前审核发布任务顺序

1. 合并长期目标与职责文档，使两个任务读取同一标准。
2. 完成跟踪快照一致性和发布 provenance 修复。
3. 恢复 Cloudflare 最小权限 Token，验证自动部署。
4. 实现并验证 `research-dossier-v1` 的机器 Schema、受信任 CI、在线枚举复核和 `worker-config.json`；确认旧 `verify` 不再响应 PR，并把 `test-and-build` 与 `research-boundary` 都加入受保护 `main` 的必需检查后，才把配置切为 `ready` 并启动 DeepSeek 首个正式批次。
5. 用 20 条试点批次校准字段和抽检规则，再允许连续生产。
