# 开发前测试需求：M3-G Provider 调用生命周期协调器

创建日期：2026-11-03；状态：实现前定义。范围：在 M3-E/F 账目模型和 Store 之上提供内部生命周期协调器；不调用 Provider、不启动 worker、不增加 API 路由、不开放 OCR 或 `document_understanding`。

## 目标与边界

Coordinator 统一处理页级 invocation 的计划、提交、成功、失败、未知、取消、显式重试和恢复查询，所有写入都带 expected state 并复用 Store 事务。它只接收已经生成的 request/config fingerprint、ProviderJobRef、usage 和 response artifact ID；不生成凭据、不猜测账单、不自动重试、不写原始响应。

计划阶段可以一次写入多个 unit，但必须先全量校验唯一 unit 和 request 摘要，失败时不留下部分计划。恢复查询只返回 `RecoveryDecision`，不改变账目。显式 retry 只有 M3-E `decide_recovery` 返回 safe_to_retry 才能提交下一 attempt。

## 验收用例

- [ ] M3G-01 / P0：计划多个 unit 前全量校验；重复 unit、缺摘要、跨 run 冲突时不留下部分记录。
- [ ] M3G-02 / P0：planned→submitted 只允许一次且 attempt=1；重复提交不创建第二条记录，expected state 冲突可见。
- [ ] M3G-03 / P0：submitted→succeeded 必须提供 response artifact；usage=0/null、billing known/unknown 保持语义。
- [ ] M3G-04 / P0：submitted→failed/unknown/cancelled 按 billing 和 ProviderJobRef 保存；unknown 不被转换成 failed 或成功。
- [ ] M3G-05 / P0：failed 显式 retry 必须经过 decide_recovery；无幂等、unknown billing、超次数均拒绝，不能静默重试。
- [ ] M3G-06 / P1：恢复查询按 unit 稳定返回 decision，不修改 updated/body；已完成为 already_complete，未发送取消为 skip。
- [ ] M3G-07 / P0：Coordinator 不调用 Provider、不接 API/worker；不把账目内容写入 ParseResult 或 capabilities。
- [ ] M3G-08 / P0：专项、完整回归、文档/契约检查和依赖审计通过；无新增依赖，OCR/document_understanding 仍未开放。

自动测试使用临时 Store 和合成 artifact ID；真实服务、worker 崩溃、远端 query/cancel、账单和响应 artifact 发布仍在开发后 TODO。开发后记录：[M3-G after](2026-11-03-m3g-invocation-coordinator-after.md)。
