# M3-E Provider 调用账目与页级恢复契约执行记录

日期：2026-11-03；环境：Windows，仓库 .venv CPython 3.12.13；无网络、无真实 Provider、无数据库迁移、无模型。需求：[M3-E before](../changes/2026-11-03-m3e-invocation-recovery-before.md)；后续：[M3-E after](../changes/2026-11-03-m3e-invocation-recovery-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_provider_runs.py -v` | 8 项通过：状态约束、恢复决策、重试闸门、取消、唯一 unit、usage/成本未知和摘要脱敏 |
| 数据库迁移 | 未执行；本阶段无 Store 变更 |
| 真实 Provider/账单 | 未执行；unknown 语义仅通过模型测试验证 |
| 新增依赖 | 0；使用现有 Pydantic/core 模型 |
| 能力清单 | 未改变，仍仅开放六种 `native_extract` |

测试证明恢复决策不会自动猜测远端状态；不能证明真实服务具备 query/cancel/idempotency，也不能证明账单状态可获取。
