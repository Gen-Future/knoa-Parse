# 解析公共核心

状态：来源/结果模型、协议、探测、JSON 约束、任务与产物存储已有初始实现；M4-A 补充了引擎无关的媒体流/时间基/PTS 契约；完整多格式对象继续按阶段扩展。

core 承载来源/产物标识、处理计划、解析器、转换引擎、内容增强与工具接口、Provider 能力接口、子任务分派、结果/错误/覆盖规则。它定义抽象，不导入具体解析器、上游框架类型、工具实现或供应商。

未来 Parser 的公开形状建议为 `probe(source)`、`plan(source, options, capabilities)`、`parse(plan, context)`；名称待技术栈确认。输入固定来源版本，输出结构化内容及完整性记录。

复合资料通过 `dispatch_child(artifact, relation, options, budget)` 的同类接口交给注册表，保留父子关系、任务限额和递归预算；不让视频模块直接 import 音频内部代码。

起步可以是单进程应用，通过 apps 注册并注入各适配器，不需要另建调度服务或复杂插件框架。

设计依据：[架构](../../../docs/architecture.md)、[Provider 接口](../../../docs/provider-interfaces.md)、[结果模型](../../../docs/result-model.md)。
