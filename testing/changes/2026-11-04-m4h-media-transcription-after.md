# 开发后不确定项：M4-H 音频执行编排

日期：2026-11-04；对应需求：[M4-H before](2026-11-04-m4h-media-transcription-before.md)。

## 已验证

- Windows FFmpeg 9.0.2 从真实合成音视频裁出 WAV，`FfmpegAudioExtractor` 保留派生 artifact 和源身份；无音轨检查在外发前阻断。
- `MediaTranscriptionRunner` 已将 extractor、外部 ASR、chunk outcome、时间偏移和 coverage/cost summary 串联；合成 Provider 失败时保留成功响应和 unknown cost。
- 结果仍是独立媒体对象，未注册 worker/API/catalog，未把 mock/合成结果写成真实转录能力。

## 仍需人工或真实服务确认

- Azure Speech 真实请求、中文/噪声/静音/重叠讲话、价格、区域和账单尚未验证。
- 当前 extractor 使用单一音轨和 PCM WAV；编码延迟、长文件、实际 VFR 音频起点、字幕合并和边界去重仍未实测。
- provider invocation 尚未接入 Store/Coordinator，崩溃恢复、query/cancel 和 worker 产品路由仍未完成。
