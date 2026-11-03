# 外部模型服务适配

按能力分为 [OCR](ocr/README.md)、[ASR](asr/README.md)、[视觉](vision/README.md)、[文档分析](document_analysis/README.md) 和 [文本模型](text_model/README.md)。供应商适配实现在对应目录内增量添加，不以供应商命名整个解析流程。

公共接口定义归 core，详见 [接口草案](../../../docs/provider-interfaces.md)。apps 注入经过配置的适配器；请求模型、凭据引用、异步任务、限制和用量保持显式。

当前已有 OpenAI/Anthropic 两种兼容协议的文本生成适配器，默认配置为硅基流动，支持自定义平台名称、地址和模型，见 [模型接入](../../../docs/model-services.md)。其他能力尚未实现；原生解析仍不调用模型。缺少服务时拒绝调用；禁止自动下载模型、本地推理或退回自建 GPU 模型服务。mock 仅用于测试，不冒充已支持解析。
