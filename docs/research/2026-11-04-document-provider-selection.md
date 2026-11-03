# 外部文档分析服务候选调查：M3-I

日期：2026-11-04。目标是选择一个可作为外部能力边界的文档分析服务，不把供应商 SDK、模型权重或供应商结果直接塞进 Knoa 公共契约。

## 当前候选：Azure AI Document Intelligence

Azure 的 Analyze Document REST API 使用 `POST .../documentModels/{modelId}:analyze`，支持 `base64Source`，返回 `202 Accepted` 和 `Operation-Location`，再通过 GET 获取异步结果；这与 Knoa 已完成的 invocation、unknown 和远端 job 恢复模型相容。[官方 Analyze Document REST API](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/analyze-document?view=rest-aiservices-v4.0+%282024-11-30%29) [官方 Get Analyze Result REST API](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/get-analyze-result?view=rest-aiservices-v4.0+%282024-11-30%29)

官方响应包含页号、页面宽高/单位、lines、words、spans、polygon、tables、figures 和 sections，能够为后续 page-region、表格和结构化目标留下足够信息。[官方响应概念](https://learn.microsoft.com/azure/ai-services/document-intelligence/concept/analyze-document-response?view=doc-intel-4.0.0) 当前实现只接收像素 polygon 文本行；无法表达的表格/图形会拒绝，直到新版结果契约完成。

选择理由是协议边界清晰、异步任务模型适配现有账目、页级坐标和结构字段足够丰富，且可以只用标准库接入，避免跨语言 SDK 和本地模型。它只是一个候选适配器，不代表已经完成供应商、区域、价格、隐私、准确率或 SLA 验收。

## 接入边界

1. `providers/document_analysis/azure.py` 只负责 HTTPS 提交、轮询、响应大小/来源校验、稳定错误码和到当前 `PageAnalysis` 的保守映射。
2. 不让 Azure JSON 直接成为公共 ParseResult；完整原始响应、派生页图、费用和远端 job 必须在产品阶段通过独立 artifact/ledger 契约保存。
3. 不将适配器加入 native worker、API、console 或能力清单，直到真实服务效果、数据边界、费用、失败/取消/恢复和迁移评审通过。
4. 保留通用 `http.py` 作为 transport 参考；不为每个供应商复制资料流程，不安装 Azure SDK。

## 后续候选比较门槛

若真实联调不满足数据区域、价格、限流、中文/扫描效果或恢复能力，继续评估同一边界下的其他外部服务。比较必须使用相同的去敏资料、相同的页图和相同的指标，不能以供应商 benchmark 或单次成功请求替代验收。
