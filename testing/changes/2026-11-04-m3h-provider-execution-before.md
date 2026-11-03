# 开发前测试需求：M3-H 页级 Provider 执行边界

创建日期：2026-11-04；状态：实现前定义。范围：在 worker 层将已计划的 invocation、单页 Provider、取消回调和 response artifact 发布顺序连接起来；不接真实 Provider、不注册到 native worker/API、不开放 OCR。

## 目标与边界

一次执行只能调用一个页一次。发送前取消记录 cancelled/not_sent；发送后取消、Provider 超时/网络错误、响应校验失败或 artifact 发布失败统一保留 unknown，不能声称远端未计费。只有 response artifact 已由调用方发布并返回 ID 后才写 succeeded。已 succeeded/cancelled/unknown 的页不会自动再次调用；批量执行保留每页独立状态。

## 验收用例

- [ ] M3H-01 / P0：planned 页提交一次，Provider 成功后先发布 response artifact，再写 succeeded；usage=0/null 正确保留。
- [ ] M3H-02 / P0：ProviderError、ParseError、未知异常只写 unknown/manual，不自动 retry，不调用第二次，不发布伪造 artifact。
- [ ] M3H-03 / P0：发送前取消不调用 Provider，billing=not_sent；发送后取消写 unknown，不写 cancelled/成功。
- [ ] M3H-04 / P0：artifact publisher 失败写 unknown；不能把 Provider 已返回当作 ParseResult 成功。
- [ ] M3H-05 / P0：已完成页不会再次调用；已 unknown 页不会自动重发，必须等待外部恢复决策。
- [ ] M3H-06 / P1：多页一页成功、一页 unknown/取消时保留逐页 outcome，不抹掉成功页。
- [ ] M3H-07 / P0：取消批次会把尚未发送的剩余页显式标记 cancelled；不产生隐藏 queued 页。
- [ ] M3H-08 / P0：专项、完整回归、文档/契约检查通过；没有新依赖/API/能力清单项目，OCR/document_understanding 仍未开放。

自动测试使用 ScriptedDocumentProvider 和合成 artifact publisher；真实服务、worker 子进程、远端 query/cancel、账单和长期恢复进入开发后 TODO。开发后记录：[M3-H after](2026-11-04-m3h-provider-execution-after.md)。
