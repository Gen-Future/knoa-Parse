# 开发前测试需求：M3-I Azure 文档分析适配器基础

创建日期：2026-11-04；状态：实现前定义。范围：为已验证的单页 PNG/JPEG 输入实现 Azure AI Document Intelligence REST adapter 的离线可测边界；不注册 native worker/API/console，不修改 `native_extract` 能力清单，不发送真实账户请求，不开放 OCR 或 `document_understanding`。

## 目标与边界

- 仅使用标准库 HTTPS/JSON transport，不引入 Azure SDK，也不加载本地 OCR、ASR、VLM 或模型权重。
- 只接受 M3-C/M3-D 产出的 `full_page_upright` 页图；提交请求只含 base64 页图和服务所需查询参数，禁止把 API key 放进 URL、日志、结果或能力声明。
- 提交必须得到 `202` 和同一 Azure resource 的 `Operation-Location`；禁止自动跟随重定向，禁止把凭据转发到不同主机、端口或协议。
- 轮询必须显式处理 `notStarted`、`running`、`succeeded`、`failed`、`cancelled`，尊重并限制 `Retry-After`，超时保留远端 job ID 且不能安全重试。
- 目前公共页级契约只能表达带像素 polygon 的文本元素。缺少几何、尺寸不匹配、表格/图形等无法无损表达的返回，必须拒绝整页，不能把丢失字段伪装成成功。
- 空页只能显式 `blank=true`；不能把空结果默认为完整 OCR。原始服务响应只在内存中提供给后续持久化阶段，本阶段不写 Store、不发布 ParseResult。

## 验收用例

- [ ] M3I-01 / P0：配置默认要求 HTTPS；本地 HTTP 只能在显式测试开关和回环地址下使用；endpoint、model ID、版本、超时和资源上限严格校验。
- [ ] M3I-02 / P0：提交路径、`api-version`、`base64Source`、媒体字节摘要和订阅密钥头正确；请求不包含原生 source ID、上下文或密钥 URL。
- [ ] M3I-03 / P0：只接受 `202`；缺少/非法 `Operation-Location`、重定向、跨主机 operation URL 都安全失败且不发生第二次请求。
- [ ] M3I-04 / P0：轮询处理中状态最终映射为成功；`Retry-After` 不得突破本地最大间隔；超出时限返回 retryable=false 且保留 operation。
- [ ] M3I-05 / P0：远端 failed/cancelled、401/403/404/429/5xx、连接错误和响应过大都归一化为稳定错误码，不暴露供应商响应正文。
- [ ] M3I-06 / P0：单页 Azure 像素坐标、页面宽高和 polygon 映射为 `PageAnalysis`；文本缺 polygon、越界、非像素单位、错误页号或尺寸比例不符时拒绝。
- [ ] M3I-07 / P0：空 `lines` 仅在没有结构化结果时映射为 `blank=true`；表格/图形等当前契约无法表达的结构明确拒绝。
- [ ] M3I-08 / P0：能力声明为 `external_service`，只列 image/png、image/jpeg 和 px；不会把适配器自动加入现有能力清单或 worker 路由。
- [ ] M3I-09 / P0：专项测试、完整 Python 回归、静态检查、依赖审计和文档检查通过；依赖增量为 0。

真实 Azure 联调、区域/隐私/保留策略、效果标注、价格核对、原始响应持久化、远端 query/cancel、调用账目接入和生产开关是后续阶段，不能由本地 HTTP 合成服务代替。
