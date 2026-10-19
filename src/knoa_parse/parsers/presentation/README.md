# PPT 与演示文稿解析

状态：初始原生路径已实现；需安装并通过 documents 组审计，后续格式和模型目标仍未启用。建议优先级：P0。属于资料家族，后续可以是同一个进程中的模块，不要求独立服务。

## 范围

首批候选：`.pptx`。后续候选：`.ppt`、`.odp`、`.key`。这些是规划，不是支持声明。

## 专用流程

按 slide 读取形状/文本/表格/备注 → 子内容分派 → 可选渲染 → 外部视觉增强。

## 定位与输出

slide index、shape ID、形状区域、备注/正文角色。

现有 v0.1.0-draft.1 不一定能表达本家族全部结构，按 [结果模型](../../../../docs/result-model.md) 升级契约后再开放相应能力。

## 依赖边界

只依赖 core 定义的接口，apps 注入成熟转换/内容增强适配、非模型工具和外部 Provider；仅按当前家族需要使用。非模型工具分组：office。按目标可能需要的外部能力：ocr、vision；不是每个文件都全部调用。不得导入其他家族内部代码；复合资料走 core 子任务分派。

## 复用候选

复用 Docling 的 PowerPoint backend 与 SimplePipeline；图表和图片增强按 Knoa 的内容引用契约组织，RAG-Anything 仅设计参考。形状、备注与分组定位必须实测，不把 Docling 节点 ID 冒充原始 shape ID。 具体边界见 [横向选型](../../../../docs/research/2026-10-15-module-selection.md) 和 [实现方案](../../../../docs/implementation-plan.md)；当前原生路径已有合成资料及任务链验收。

## 实现前验收

分组形状、SmartArt、图表、仅图片幻灯片、备注、动画与阅读顺序；模型描述不能替代底层数值。

共同规则见 [处理流程](../../../../docs/pipelines.md) 与 [评测计划](../../../../evals/README.md)。
