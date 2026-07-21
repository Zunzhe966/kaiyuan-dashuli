# Batch 6：长尾暂缓清零

- 日期：2026-07-22
- 对应：S9

## 入库

| id | domain | 原状态 | 说明 |
|---|---|---|---|
| surrealdb | databases | deferred | BUSL；多模型差异写清 |
| zabbix | observability | deferred | AGPL；传统监控 vs 云原生 |
| minio | devops | 新缺口 | S3 对象存储 AGPL |
| seaweedfs | devops | 新缺口 | Apache 对象/文件存储 |
| flower | backend | 新缺口 | Celery 监控 UI |

## 明确拒绝 / 维持不录

| name | decision | reason |
|---|---|---|
| AutoGPT | rejected | Polyform Shield / 平台与社区许可分裂，选型不稳定 |
| GlitchTip | rejected | 上游仓长期停滞（约 2022），不达维护门槛 |
| Grafana OnCall | rejected | `grafana/oncall` 指向已归档 cold-storage |
| Unity / Unreal | rejected | 引擎主体非开源选型 |

## 仍可下轮

| name | note |
|---|---|
| 更多 GIS/IoT/媒体长尾 | 按 taxonomy 继续，不阻塞本步 |
