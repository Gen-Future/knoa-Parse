# 测试需求与人工验收

这里保存“要验证什么、怎样验证、什么算通过”。自动测试代码仍在 tests，确定性格式评测仍在 evals；这里不复制测试实现，也不把历史通过记录当作本次人工通过。

## 当前验收包

日期：2026-10-19。范围：六格式原生解析、任务服务、可选工作台、外部文本模型与模型设置。当前 Demo 免登录；原生解析不调用模型，模型生成尚不属于文档增强。以 [实施记录](../docs/implementation-status.md)、[模型说明](../docs/model-services.md) 为边界。

1. 阅读 [本轮目标与验收准备](current/00-scope-and-preparation.md)。这是现有工程的补建基线，不冒充开发前已完成的需求定义。
2. 按 [解析内容与追溯](current/01-parsing.md) 验证资料。
3. 按 [任务与工作台](current/02-runtime-and-console.md) 验证完整使用链路。
4. 按 [模型服务与配置](current/03-model-services.md) 验证独立模型入口。
5. 最后处理 [开发后不确定项](current/04-uncertainties.md)，逐项决定修复、限制或延期。

每条用例都有唯一 ID、优先级、操作与预期。每个 `- [ ]` 仅在留存证据并满足全部预期后勾选；失败、阻塞或明确限制不勾选。详细结论另存执行记录，复验保留旧记录。建议依次做 P0 → P1 → P2，不必一次做完。

当前共 69 项：解析与追溯 26 项、任务与工作台 19 项、模型服务 12 项、开发后不确定项 12 项。

## 后续工程规则

已按此流程实施的工程：[M3-A 开发前需求](changes/2026-10-19-m3-foundation-before.md)、[开发后不确定项](changes/2026-10-19-m3-foundation-after.md)、[验证记录](records/2026-10-19-m3-foundation.md)。

当前工程：[M3-B 开发前需求](changes/2026-10-22-m3b-http-provider-before.md)、[开发后不确定项](changes/2026-10-22-m3b-http-provider-after.md)、[验证记录](records/2026-10-22-m3b-http-provider.md)。

当前工程：[M3-C 开发前需求](changes/2026-11-02-m3c-page-input-before.md)、[开发后不确定项](changes/2026-11-02-m3c-page-input-after.md)、[验证记录](records/2026-11-02-m3c-page-input.md)。

当前工程：[M3-D 开发前需求](changes/2026-11-02-m3d-renderer-boundary-before.md)、[开发后不确定项](changes/2026-11-02-m3d-renderer-boundary-after.md)、[验证记录](records/2026-11-02-m3d-renderer-boundary.md)。

- 实现前创建 `testing/changes/YYYY-MM-DD-主题-before.md`，使用 [开发前模板](templates/before-development.md)。需求、样本与独立预期先于实现；任务开始时尚有疑问，先写待决事项和禁止做出的假设。
- 工作结束创建同名前缀的 `-after.md`，使用 [开发后模板](templates/after-development.md)，单独列出不确定部分，链接原需求与自动验证证据。新增风险不能只埋在交付对话里。
- 行为范围调整时更新 before 并记录原因；after 不得降低原验收条件来消除失败。
- 未能覆盖的关键目标列为阻塞；适用范围、已知缺口与延期必须明示。没有新增不确定项时也保留 after，说明检查范围和依据。
- 用 [执行模板](templates/execution-record.md) 留存逐项结果：未执行、通过、失败、阻塞、不适用。发现问题写实际与预期差异、复现材料及后续复验。

## 资料与证据存放

合成且不含密钥的需求、执行摘要可放 `testing/records/`。真实文件、完整结果、截图、日志、账户配置放已忽略的 `.local/manual-testing/批次名/`，不要提交原件或真实凭据。记录可使用匿名样本 ID 和 SHA256 关联本地证据。

建议样本命名 `格式-特性-序号`，每份写明作者工具/版本、页或表结构、预先标出的关键内容、合法使用依据及摘要。不要只挑“看上去输出正常”的文件，也不要用模型生成答案作为原件正确性的唯一标准。
