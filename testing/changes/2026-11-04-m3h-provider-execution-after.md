# 开发后不确定项：M3-H 页级 Provider 执行边界

日期：2026-11-04；关联 [开发前需求](2026-11-04-m3h-provider-execution-before.md)、[执行记录](../records/2026-11-04-m3h-provider-execution.md)、[M3-G 生命周期协调器](2026-11-03-m3g-invocation-coordinator-after.md)。

## 已验证事实

8 项专项测试验证成功发布顺序、Provider/Publisher 异常、发送前后取消、unknown 账目、已完成幂等、多页 partial 和剩余页取消。执行器只接受显式 Provider 和 publisher，不改变现有 native worker 路由。

## 不确定项与 TODO

- [ ] **M3H-UNC-01 / P0 / 真实 worker 子进程**。当前执行器在调用方进程运行；需要在受控 worker 子进程中验证超时、强杀、临时 artifact 清理和账目状态。
- [ ] **M3H-UNC-02 / P0 / Provider 远端 job**。异步 Provider 需要在 submit 后保存 job ID，再由 query/cancel 适配器恢复；当前执行器只支持一次同步调用。
- [ ] **M3H-UNC-03 / P0 / response artifact 发布事务**。需定义 artifact 发布、账目 succeeded 和最终 ParseResult/coverage 的事务顺序；当前 publisher 只返回抽象 ID。
- [ ] **M3H-UNC-04 / P1 / 费用和重试**。unknown billing 仍人工处理；真实服务验证幂等、账单和安全 retry 后才能开放自动恢复。
- [ ] **M3H-UNC-05 / P1 / UI/主仓消费**。执行 outcome 尚未进入 API/console 或主仓新契约，不能显示为用户可用 OCR 结果。

## 收尾结论

M3-H 完成页级执行顺序和未知状态保护，未完成真实 Provider、worker 子进程和产品路由。下一阶段应先完成一个真实外部文档服务的选型/专用 adapter，再接入执行器。
