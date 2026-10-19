# 按资料类型组织的解析流程

13 个独立家族见 [资料类型](../../../docs/formats.md)；[catalog.json](catalog.json) 记录目录、优先级、首批/后续格式以及潜在工具和外部能力。

catalog schema v2 将规划后缀与 enabled_extensions 分开；当前验收 .txt/.json/.docx/.pptx/.xlsx/.pdf 的原生目标；运行可用性另受文档依赖组审计约束。文件不参与引擎动态加载，检查工具核对运行时能力声明。

每个家族负责自己的流程、选项、产物与验收，不代表每类都从底层库重新开发。只能通过 core 接口使用 engine、enrichment、工具、Provider 和子任务分派；不直接导入另一家族或上游框架，也不把 OCR/ASR 供应商 SDK 嵌进格式代码。

成熟项目的转换与内容增强跨家族复用，策略见 [ADR 0004](../../../docs/adr/0004-selective-module-integration.md)。catalog 记录资料与能力需求，不记录实际引擎绑定；未来运行时注册与支持声明需在集成验收后实现。

新增家族时补充目录 README、catalog 条目、位置模型和 evals；只增加同一家族的扩展名不必创建新包。机器检查验证声明一致性和 Python 源码导入边界。
