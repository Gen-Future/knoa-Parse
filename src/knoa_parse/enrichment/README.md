# 上下文与外部增强

状态：已实现内部 M3-A 页级外部文档编排基础，入口为 document.analyze_pages；没有迁入第三方源码，也未进入产品解析路由。输入约束、预算、取消和报告见 [实现说明](../../../docs/m3-document-analysis.md)。

只负责按结构位置选择附近标题、正文、图注或时间片段，保存上下文引用、预算、截断和外部调用结果。返回证据关联，不只返回拼接字符串；生成说明与原文分开保存。

RAG-Anything 的上下文与模态关联作为设计参考，当前不依赖其包、不搬运 ContextExtractor 或整套处理器，不引入 LightRAG、索引、图谱或本地模型。有限的上下文选择按 Knoa 契约实现；未来源码迁移必须单独证明收益和可分离范围。

只通过 core 接口调用 Provider 与工具，由 apps 注入。缺少服务、无有效上下文或预算不足须明确记录，不能以空字符串伪装成功。

参见 [实现方案](../../../docs/implementation-plan.md)、[横向调查](../../../docs/research/2026-10-15-module-selection.md) 与 [接入决策](../../../docs/adr/0004-selective-module-integration.md)。
