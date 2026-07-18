# 静态目录发布与回滚

## 系统边界

- GitHub 是源文件、设计历史和验证记录的备份，不保存服务器运行状态。
- `build/` 全部是可重新生成的临时产物，可以删除。
- 搬瓦工只保存解压后的静态文件；最多保留最新三个已校验版本。
- 网站不在服务器运行爬虫、模型、数据库、动态搜索或反馈服务。
- GitHub Actions 只验证和生成 7 天临时制品，不自动公开或部署。

## 本地发布

仓库当前只要求 Python 3.12 和 `requirements.txt`。依次运行：

```bash
.venv/bin/python scripts/validate_graph.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/export_catalog_v1.py
.venv/bin/python scripts/build_static_site.py --output build/site --base-url https://example.invalid
.venv/bin/python scripts/build_release.py --site build/site --output build/releases
shasum -a 256 build/releases/*.tar.gz
```

真正公开前，把 `https://example.invalid` 替换为用户确认的正式域名，再重新生成。上传前必须核对压缩包 SHA-256 与对应 manifest 完全一致。

## 服务器目录与回滚

建议目录：

```text
/srv/kai-yuan-da-shu-li/
├── releases/<git-commit>/
└── current -> releases/<git-commit>/
```

新版本先解压到独立的提交目录，校验文件数量和散列，再原子更新 `current` 软链接。回滚只把 `current` 改回上一个已验证目录，然后做一次本机回环请求。禁止覆盖旧目录后再尝试回滚。

## 部署闸门

以下条件全部满足后才允许部署：

1. 用户确认正式域名或公开路径。
2. 当前 Nginx 和 Xray 配置已经备份。
3. 新配置通过 `nginx -t`。
4. 静态源站保持在 `127.0.0.1:8088`，不改动 Xray 已使用的监听端口。
5. `curl http://127.0.0.1:8088/` 和一个 `/api/v1/nodes/*.json` 回环检查成功。
6. 现有前门或 Cloudflare Tunnel 只把网站域名转发到该回环端口。

公开请求不能直接到达 Sub2API、CPA、PostgreSQL 或 Redis。部署失败时先恢复配置，再把 `current` 链接切回前一版本。
