# 开发后不确定项：M3-F Provider 账目 SQLite 持久化

日期：2026-11-03；关联 [开发前需求](2026-11-03-m3f-ledger-store-before.md)、[执行记录](../records/2026-11-03-m3f-ledger-store.md)、[M3-E 契约](2026-11-03-m3e-invocation-recovery-after.md)。

## 已验证事实

填写完成后记录旧 schema 迁移、事务写入、幂等/冲突、状态终态、并发、read-only 和完整回归证据。真实 Provider、远端 job 查询/取消和计费仍不属于本阶段。

## 不确定项与 TODO

- [ ] **M3F-UNC-01 / P0 / 生产数据库迁移**。需要在用户已有数据目录、备份和异常中断场景验证迁移；当前自动测试只覆盖临时数据库。
- [ ] **M3F-UNC-02 / P0 / worker 集成**。Store 已能保存账目后，worker 仍未创建/更新 invocation；接入前需定义租约、崩溃恢复、远端 query 和 artifact 发布顺序。
- [ ] **M3F-UNC-03 / P1 / 保留与清理**。需要定义 invocation、远端引用、usage 和原始响应 artifact 的保留/删除策略，避免凭据或敏感资料长期残留。
- [ ] **M3F-UNC-04 / P0 / API/console 暴露**。当前不提供账目 API；未来若展示恢复状态，需脱敏字段、权限和 unknown/manual 交互验收，不能让界面暗示已取消或未计费。
- [ ] **M3F-UNC-05 / P0 / 真实费用**。数据库能保存 cost/usage 不代表账单正确；真实服务联调前仍需定义供应商账单核对。

## 收尾结论

M3-F 只提供持久化基础和迁移边界；真实 Provider、worker 恢复、API/console 和费用验收仍阻塞 `document_understanding` 开放。
