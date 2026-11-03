# 开发后不确定项：M3-I Azure 文档分析适配器基础

日期：2026-11-04；对应需求：[M3-I before](2026-11-04-m3i-azure-adapter-before.md)。

## 已验证

- 标准库 REST adapter 可提交单页 base64Source，接收并校验同资源 operation URL，轮询处理中状态并映射成功/空页/失败/取消。
- 已覆盖 API key 只放在请求头、无重定向、响应大小限制、远端 job ID 保留、Retry-After 上限、超时不安全重试和稳定错误码。
- 只将带像素 polygon 的文本行映射为现有 `PageAnalysis`；表格、图形和其他无法无损表达的结构会拒绝，不会静默丢失。
- 适配器未注册到 worker、API、console 或能力目录；没有真实 Azure 请求和新依赖。

## 仍需人工或真实服务确认

- Azure 资源的区域、数据处理/保留、身份认证、限流、SLA、价格和 API 版本升级策略尚未在项目账户上核对。
- 不同输入格式、扫描 PDF、复杂旋转/裁切、中文与表格的真实效果尚无去敏标注集；不能报告 OCR 准确率或完整文档理解能力。
- Azure 返回的完整 `analyzeResult` 尚未持久化，当前公共契约会拒绝表格/图形；需要先定义新版 `document_understanding` 结果与原始响应 artifact 关系。
- `analyze_page` 仍是同步 facade；真实 worker 需要把 `AzureOperation.remote_job_id` 写入调用账目，支持崩溃恢复、query/cancel 和未知计费状态。
- 当前按单页图提交，服务返回 page number 预计为 1；多页 PDF 直传、页级费用、服务端重试和完整 source 到页图几何校准未实现。

这些不确定项保持 TODO，不能因离线适配器测试通过而开放 OCR 或 `document_understanding`。
