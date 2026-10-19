# 成熟项目转换适配

状态：Docling 原生路径已有运行适配与合成资料验收；不引入本地模型。

封装 Docling 等成熟项目的完整转换能力：选择允许的 pipeline、执行转换、保留完整上游产物并映射 core 证据模型。首要实验对象是 Docling 的原生格式 backend、SimplePipeline 和 NativePdfPipeline。

接口在 core，apps 注入具体实现；parsers 不直接导入上游类型。engine 可依赖经审查的上游公开接口，不能引入本地模型或假设关闭 OCR 就关闭了全部模型。

默认只保留一个通用文档引擎，选定精简非模型路径。外部模型由 parser/enrichment 通过 core Provider 接口编排，不改造完整标准模型管线；不把供应商客户端放进 engine。XLSX 原始语义按实现方案有限补充。优先依赖调用，只有具体缺口证明收益时才评估最小补丁或源码抽取。

参见 [实现方案](../../../docs/implementation-plan.md) 与 [横向调查](../../../docs/research/2026-10-15-module-selection.md)。
