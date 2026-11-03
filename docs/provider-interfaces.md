# 外部模型能力接口草案

本文件保留完整接口设计。同步文本生成最小接口已在 core/text_model.py 实现，具体适配位于 providers/text_model，apps 负责配置和注入。M3-A 已在 core/document_analysis.py 实现同步单页文档分析内部协议及独立编排，M3-E 在 core/provider_runs.py 增加 persistence-neutral 调用账目和保守恢复决策，见 [实现边界](m3-document-analysis.md)；无真实文档 Provider，未进入产品路由。其余异步与多模态协议仍为规划。默认无服务凭据，不进行外部调用；显式文本调用方式见 [模型接入](model-services.md)。

## 能力划分

| 接口 / 目录 | 输入意图 | 标准结果 | 必须查询的能力 |
| --- | --- | --- | --- |
| OcrProvider / ocr | 识别页图/图片上的文字 | 行/词、区域、语言、可选置信度 | 输入格式、字节/像素限制、坐标单位、语言、是否有字级框 |
| AsrProvider / asr | 转录指定音轨或片段 | 文本、时间段、可选词级时间/说话人 | 同步/异步、语言、时长上限、时间戳粒度、diarization |
| VisionProvider / vision | 理解图片/采样帧，必要时原生视频 | 带输入引用的描述/观察结果 | 是否接受视频、图像数、分辨率、结构化输出、定位能力 |
| DocumentAnalysisProvider / document_analysis | 一体化处理 PDF/页图/受支持文档 | 块、表格、页面区域及阅读顺序 | 格式、页数、表格、坐标/文本跨度、异步任务 |
| TextModelProvider / text_model | 可选结构修复、格式归一化等增强 | 原内容引用、变换结果及变换说明 | 上下文上限、结构化输出、用量与模型版本 |

同一供应商可实现多个接口。文档分析可以包含 OCR/版面/表格，不能为了凑齐接口重复收费调用。TextModelProvider 默认不参与纯文本读取，不承担长期记忆提取、用户画像或 embedding。

## 共同协议形状

以下是待类型化的逻辑接口，方法名不是公共 API 承诺：

```text
describe() -> CapabilityDescriptor
submit(WorkItem, RequestContext) -> CompletedResult | PendingJob
poll(ProviderJobRef, RequestContext) -> PendingJob | CompletedResult | FailedResult
cancel(ProviderJobRef, RequestContext) -> CancelOutcome
```

同步服务直接返回结果，异步服务保留可恢复的远端 job 引用。取消不是必定成功的承诺；已经发生的计费在用量记录中保留。未来如需实时 ASR，新增流式会话接口，不假装文件 submit 已经支持流式。

| 对象 | 最少需要表达的内容 |
| --- | --- |
| CapabilityDescriptor | provider/版本、operation、输入格式和限制、同步/异步、输出粒度、坐标/时间约定、已实现能力、是否 external_service |
| WorkItem | artifact 引用、来源/派生关系、页或时间选择、解析选项、输出能力需求 |
| RequestContext | 授权/租户作用域、凭据引用、允许的服务/区域、超时与取消、最大用量、追踪标识、幂等标识 |
| ProviderJobRef | provider、远端 job ID、配置版本、可恢复状态；不含凭据 |
| CompletedResult | 归一化内容、输入定位、model/provider 版本、usage、原始响应 artifact 引用、warnings |
| FailedResult | 稳定错误代码、失败单元、可重试性、建议退避信息；不泄漏输入和秘密 |

调用方传 `credential_ref` 而非在结果、任务日志或 catalog 中存 API key。文件传输可用受控字节流、临时上传或短期签名 URL；Provider 不能随意抓取 WorkItem 中的未授权网址。

## 必须做的归一化

- 外部字符偏移可能是 UTF-16、字节或 code point；明确原始单位并映射，不直接套到主契约。
- bbox 可能是像素、点、英寸或归一化比例；保留原始坐标系和派生变换，再生成规范位置。
- 分段 ASR 的时间加原始片段偏移；说话人 ID 局部作用域保持明确。
- 置信度缺失则留缺失；不同服务的数值不当作统一概率。模型描述标记为 inferred，不和原文提取混合。
- 第三方缺少必要定位时报告缺口；不能通过推测位置伪造证据。

## 调用与回退策略

先检查服务能力、输入上限和剩余预算，再发送资料。超限可切分的输入保留映射后分段，不能切分则明确失败。仅对允许的临时错误重试，受最大次数、总时限和总预算约束；异步任务优先恢复轮询，不在超时后盲目重交付费任务。

幂等分两层：本地任务/产物去重和供应商请求去重；供应商没有幂等能力时不能承诺不重复计费。缓存必须按授权作用域、内容、配置与模型版本隔离，凭据轮换不把旧授权永久带入缓存。

缺少外部服务时，不回退 Tesseract、PaddleOCR、Whisper、本地 VLM、ONNX 或其他推理实现。使用 CPU 的模型同样被排除。mock Provider 仅用于合成响应验证，要明确 `mock` 标记，不能作为产品解析成功。

## 后续适配器验收

用合成响应验证时间/坐标换算、429/超时/永久错误、重复投递、任务恢复、取消、缺失字段及使用量计数。真实调用单独报告实际账户区域、模型版本、资料范围和成本；没有真实调用就不报告真实服务效果。
