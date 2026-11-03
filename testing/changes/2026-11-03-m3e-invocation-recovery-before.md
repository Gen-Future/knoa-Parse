# 开发前测试需求：M3-E Provider 调用账目与页级恢复契约

创建日期：2026-11-03；状态：实现前定义。范围：core 内部 ProviderInvocation/页级运行账目、状态迁移和恢复决策；不接真实服务、不改 SQLite、不接 API/worker、不开放 OCR 或 `document_understanding`。

## 目标与边界

每个页级调用必须记录输入摘要、Provider/config/request 标识、attempt、状态、远端 job 引用、可重试性、计费状态、用量、错误码和响应 artifact 引用。凭据、原始请求 body、原始响应 body 不进入账目。账目区分“未发送”“已发送但结果未知”“已完成”“可安全重试”，恢复决策必须显式返回，不能由调用方猜测。

同步调用没有远端查询能力时，timeout/连接中断/进程崩溃后的 `unknown` 一律人工处理；只有明确未发送，或服务提供幂等且账目允许时，才可自动重试。`retryable` 只是服务错误提示，不得绕过 billing 状态和最大尝试次数。

## 验收用例

- [ ] M3E-01 / P0：账目保存唯一 ID、run/unit/provider/operation、输入与请求摘要、配置版本；JSON/repr 不出现 key、body、路径或响应原文。
- [ ] M3E-02 / P0：planned→submitted→succeeded/failed/unknown/cancelled 合法；成功必须有 attempt，失败必须有稳定 error_code，成功响应可绑定 artifact。
- [ ] M3E-03 / P0：禁止 succeeded→submitted、cancelled→submitted、planned→succeeded 等跳跃和回退；重复同一终态更新保持幂等或明确冲突。
- [ ] M3E-04 / P0：submitted/unknown 且有远端 job/query 能力只返回 query_remote；没有查询能力返回 manual_review，不能自动重试。
- [ ] M3E-05 / P0：failed + 明确未计费 + retryable + attempt 未超限才返回 retry；unknown billing 或无幂等能力必须 manual_review。
- [ ] M3E-06 / P0：cancelled 未发送可 skip；已发送但计费未知必须 manual_review，不报告远端已取消或未计费。
- [ ] M3E-07 / P1：成功记录 usage=0 与 usage=null 区分；cost 未知保持 null；响应 artifact 只能在 succeeded 绑定。
- [ ] M3E-08 / P0：同一 run 的 unit ID 不重复；ledger snapshot 稳定排序，恢复决策不修改账目。
- [ ] M3E-09 / P1：ProviderJobRef 不含凭据，可表达 query/cancel/idempotency 能力；远端 job ID 可恢复但不代表已完成。
- [ ] M3E-10 / P0：无数据库变更、无新增依赖；现有回归和能力清单保持不变，OCR/document_understanding 仍未开放。

自动测试只验证内部状态与决策，不验证真实远端查询、取消、计费或崩溃恢复。开发后记录：[M3-E after](2026-11-03-m3e-invocation-recovery-after.md)。
