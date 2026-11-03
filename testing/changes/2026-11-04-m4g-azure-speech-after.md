# 开发后不确定项：M4-G Azure Speech 外部 ASR 适配器

日期：2026-11-04；对应需求：[M4-G before](2026-11-04-m4g-azure-speech-before.md)。

## 已验证

- Azure Speech 2025-10-15 multipart adapter 已接入现有 `AsrRequest`/`AsrResponse`，词级时间和 speaker 会加片段偏移映射；标准库即可运行。
- 本地 HTTP 合成服务覆盖 multipart、definition、key 隔离、请求上限、状态错误、非法响应和越界词；没有真实账户调用。
- Azure Speech 费用保持 unknown/null，adapter 没有把一次 HTTP 成功写成 ParseResult 或产品能力。

## 仍需人工或真实服务确认

- 尚未验证真实 Azure 资源的区域、权限、数据保留、中文/多语言效果、diarization、价格和服务限额。
- 当前 API 是同步快转录，超过切片上限需由 FFmpeg chunk planner 管理；异步 batch、query/cancel、账目、重试和分段去重尚未接入。
- 真实语音标注集、噪声/静音/重叠讲话和外部缺段仍缺证据，因此 `transcribe` 目标继续关闭。
