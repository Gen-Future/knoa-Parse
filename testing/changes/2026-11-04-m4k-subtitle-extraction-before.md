# 开发前测试需求：M4-K 容器字幕提取

创建日期：2026-11-04；范围：使用受控 FFmpeg 从 subtitle stream 提取 WebVTT，并接入已有字幕时间线解析；不把字幕当 ASR，不修改旧 ParseResult。

- [ ] 只接受已探测的 subtitle stream，源摘要前后校验，输出受限。
- [ ] FFmpeg 缺失、超时、非零、编码非法和空输出稳定失败。
- [ ] 提取结果保留 source_id/language/cue 时间，SRT/WebVTT parser 负责结构校验。
- [ ] 专项、静态检查、完整回归通过；视频/转录能力仍未公开。
