# M3-F Provider 账目 SQLite 持久化执行记录

日期：2026-11-03；环境：Windows，仓库 .venv CPython 3.12.13；使用临时 SQLite，不接网络、Provider、worker 或 API。需求：[M3-F before](../changes/2026-11-03-m3f-ledger-store-before.md)；后续：[M3-F after](../changes/2026-11-03-m3f-ledger-store-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_provider_store.py -v` | 7 项通过：旧 schema 迁移、幂等/冲突、状态迁移、终态、筛选、read-only 和并发写入 |
| M3-E 内存契约回归 | 8 项通过 |
| 完整回归 | 待本阶段收尾后填写 |
| 旧 schema 迁移 | 临时旧 schema 迁移通过；生产数据目录未迁移 |
| 新增依赖/API | 0；账目不进入现有路由 |

真实 Provider、计费、worker 崩溃恢复和长期保留保持未执行。
