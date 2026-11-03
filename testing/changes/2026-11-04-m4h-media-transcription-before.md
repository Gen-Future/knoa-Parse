# 开发前测试需求：M4-H 音频执行编排

创建日期：2026-11-04；状态：实现前定义。范围：把已探测音轨、受限 chunk、真实 FFmpeg 音频裁剪、注入 ASR 和覆盖/费用摘要串成独立的转录编排器；不注册 API/worker、不发送真实 Azure 请求、不修改 ParseResult。

## 目标与边界

- FFmpeg 按 chunk 的 request 区间输出受限 PCM WAV，保留 source SHA 和派生 artifact；进程失败、超时、输出超限和源变化稳定失败。
- 编排器先做音轨/时长/分段计划，再逐 chunk 调用 extractor 与外部 `AsrProvider`；保留成功响应、失败 chunk 和 unknown 费用。
- ASR 结果独立保存为 `MediaTranscriptionResult`，summary 只以 core 区间计覆盖；重叠上下文由 planner 处理，后续去重仍不自动删除文本。
- 无音轨在 extractor/Provider 前失败；Provider timeout/unavailable 后不自动重试，cost=null；真实 worker/ledger/query/cancel 留后续产品阶段。

## 验收用例

- [ ] M4H-01 / P0：真实 FFmpeg 从带音轨 MP4 裁出 WAV，artifact SHA/大小/媒体类型正确，chunk 请求上限受控。
- [ ] M4H-02 / P0：音轨缺失、源摘要变化、FFmpeg 缺失/超时/非零/空输出稳定失败，不调用 ASR。
- [ ] M4H-03 / P0：编排器逐 chunk 传递源时间、语言、词级/diarization 和幂等键，保留成功响应与失败 chunk。
- [ ] M4H-04 / P0：部分 Provider 失败产生 partial/missing ranges；timeout 后费用 unknown/null，成功响应不丢失。
- [ ] M4H-05 / P0：真实合成音视频、专项、完整回归、静态检查、lock/依赖审计通过；不开放 transcribe。

真实 Azure Speech、真实中文语音集、账单/重试恢复、worker/API/console 路由和 ParseResult 新契约留在后续产品阶段。
