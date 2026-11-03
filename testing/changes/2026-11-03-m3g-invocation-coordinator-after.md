# 开发后不确定项：M3-G Provider 调用生命周期协调器

日期：2026-11-03；关联 [开发前需求](2026-11-03-m3g-invocation-coordinator-before.md)、[执行记录](../records/2026-11-03-m3g-invocation-coordinator.md)、[M3-F 持久化](2026-11-03-m3f-ledger-store-after.md)。

## 已验证事实

填写完成后记录计划原子性、状态迁移、显式 retry 闸门、恢复查询无副作用和 Coordinator 无 Provider/API 依赖。真实服务与 worker 仍不属于本阶段。

## 不确定项与 TODO

- [ ] **M3G-UNC-01 / P0 / worker 调用顺序**。需要决定提交 invocation、发送远端请求、保存远端 job ID、发布响应 artifact 的事务边界；Coordinator 当前只接受调用方提供的结果。
- [ ] **M3G-UNC-02 / P0 / 崩溃窗口**。在 planned/submitted/unknown/response artifact 发布前终止 worker，验证重启后的 query/manual/retry 决策和租约归属。
- [ ] **M3G-UNC-03 / P0 / 真实 Provider 语义**。真实服务的同步响应、异步 job、幂等、query/cancel 和 usage/cost 字段需要专用 adapter 映射，不能由通用 Coordinator 猜测。
- [ ] **M3G-UNC-04 / P1 / API/console 展示**。恢复 decision 未来若暴露给用户，需要脱敏和明确 unknown/manual 文案，不能把“可查询”显示为“已完成”。
- [ ] **M3G-UNC-05 / P1 / 多页一致性**。页级成功/失败与 ParseResult coverage、artifact 发布和最终 partial 的合并规则尚未接入。

## 收尾结论

M3-G 只统一内部生命周期写入和恢复查询，不代表 Provider 已接入，也不代表 worker 能自动恢复。后续真实接入前必须完成崩溃窗口和账单证据验收。
