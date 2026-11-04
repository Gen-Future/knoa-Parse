# 开发后不确定项：M4-J 媒体调用账目装配

日期：2026-11-04；对应需求：[M4-J before](2026-11-04-m4j-media-ledger-assembly-before.md)。

- apps/worker 已提供唯一的 `execute_media_transcription` 装配入口，runner 可持久化每个 chunk 的生命周期。
- 真实 worker job target、artifact publisher、远端 query/cancel 和 Azure 账户仍未接入；公开能力继续关闭。
- 现有 Store 状态和媒体 summary 已分别验证，跨进程崩溃恢复需在真实 media job 路由阶段继续验收。
