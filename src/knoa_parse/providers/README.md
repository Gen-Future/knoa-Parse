# 外部模型服务适配

按能力分为 [OCR](ocr/README.md)、[ASR](asr/README.md)、[视觉](vision/README.md)、[文档分析](document_analysis/README.md) 和 [文本模型](text_model/README.md)。供应商适配实现在对应目录内增量添加，不以供应商命名整个解析流程。

公共接口定义归 core，详见 [接口草案](../../../docs/provider-interfaces.md)。apps 注入经过配置的适配器；请求模型、凭据引用、异步任务、限制和用量保持显式。

当前没有任何真实适配器、账号配置或模型调用。缺少服务时拒绝必需能力或返回明确的部分结果；禁止自动下载模型、本地推理或退回自建 GPU 模型服务。mock 仅用于测试，不冒充已支持解析。
