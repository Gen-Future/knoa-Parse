# 开发前测试需求：M4-J 媒体调用账目装配

创建日期：2026-11-04；范围：把 M4 转录 runner 通过 apps/worker 装配到现有 Store/InvocationCoordinator；不开放 API target，不绕过真实 ASR 闸门。

- [ ] 每个 chunk 先计划 invocation，再提交外部 Provider；成功必须先发布 response artifact 后写 succeeded。
- [ ] Provider 超时/取消后写 unknown，提取失败或发送前取消不得伪造成功。
- [ ] runner 仍保留 total deadline、chunk coverage、unknown cost 和边界去重。
- [ ] 装配入口只能由 apps 注入 Store、Provider、Extractor 和 publisher；core/processor 不依赖 apps。
- [ ] 专项、完整回归和静态检查通过；公开 API/能力清单保持关闭。
