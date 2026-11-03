# 开发后不确定项：M3-E Provider 调用账目与页级恢复契约

日期：2026-11-03；关联 [开发前需求](2026-11-03-m3e-invocation-recovery-before.md)、[执行记录](../records/2026-11-03-m3e-invocation-recovery.md)、[能力闸门](../../docs/TODO.md)。

## 已验证事实

8 项测试验证账目字段约束、合法终态、禁止回退、unknown/query/manual 决策、重试条件、取消语义、usage 0/null 区分、唯一 unit 和稳定 snapshot。实现位于 `core/provider_runs.py`，是无数据库、无 Provider 调用的 persistence-neutral contract。

## 不确定项与 TODO

- [ ] **M3E-UNC-01 / P0 / SQLite 迁移**。需设计 invocation_runs、provider_refs、usage 与响应 artifact 关系的迁移版本；验证旧数据库启动、重复迁移、事务原子性和并发 worker。当前账目只在内存模型中存在。
- [ ] **M3E-UNC-02 / P0 / worker 崩溃恢复**。在 submitted/unknown/failed 状态中终止 worker，重启后验证 query/retry/manual 决策和租约归属；不得依靠任务重跑覆盖账目。当前没有产品路由。
- [ ] **M3E-UNC-03 / P0 / 真实远端幂等**。选择服务后核对 idempotency key、远端 query/cancel、配置版本和 job ID 生命周期；服务没有幂等时不能把本地 retry 标为安全。
- [ ] **M3E-UNC-04 / P0 / 计费证据**。验证 timeout、连接断开、服务 5xx、取消后的实际账单状态；账目必须允许 unknown，不能用 token=0 或 cost=0 填补。
- [ ] **M3E-UNC-05 / P1 / 长期保留与脱敏**。定义 invocation 保留期限、原始响应 artifact 权限、日志字段和密钥轮换后的可追溯关系；当前 snapshot 不写入任何 secret/body/path。
- [ ] **M3E-UNC-06 / P0 / 产品契约与路由**。把 ledger 接入 Store/worker/API/console 前，先定义 `document_understanding` 新结果版本、页级 coverage 合并、恢复 UI 和主仓消费影响。当前能力清单仍不开放 OCR。

## 收尾结论

M3-E 完成了保守恢复决策和账目数据模型，未完成持久化、真实远端恢复、账单验证和产品接入。未知远端状态默认进入人工处理路径，避免自动重复计费。后续实现必须先补 SQLite/worker 的开发前需求。
