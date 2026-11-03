# 解析服务入口（可选）

状态：单用户 API 已实现。使用同一 Store/worker，当前单用户 Demo 默认不鉴权；项目内 `.local/server.json` 只配置数据目录。文档与运行命令见 [仓库 README](../../../../README.md)。

接收原件、创建原生解析任务、读取状态/结果及下载产物；独立文本模型接口为 `/v1/models/text`。默认硅基流动，支持 OpenAI/Anthropic 兼容平台的自定义配置，见 [模型与服务配置](../../../../docs/model-services.md)。

API 负责入口装配，原生解析交由独立 worker；文本模型调用为同步请求。可选工作台挂载同一个 API，路径带 `/api` 前缀。

模型接口通过 core 协议注入供应商适配器，保持与证据契约、原生解析及界面独立。
