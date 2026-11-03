# 开发后不确定项：M4-D 音频分段与字幕时间线

日期：2026-11-04；对应需求：[M4-D before](2026-11-04-m4d-timeline-before.md)。

## 已验证

- 音频 chunk 规划以 `max_segment_ms - 2*overlap_ms` 推进 core 区间，前后上下文仍受请求上限约束；无音轨/无 duration 会阻断计划。
- SRT 和 WebVTT 的毫秒时间、多行 cue、VTT settings、顺序和错误语义有离线测试；字幕保持独立，不伪装 ASR。

## 仍需人工或真实环境确认

- 尚未从 MP4/MKV/MOV 容器真实抽取字幕，字幕编码、样式标签、重叠 cue、超长 cue 和多个字幕流尚无样例验收。
- 音频 chunk 尚未通过 FFmpeg 实际裁剪；边界样本、编码器延迟、静音、重叠 ASR 输出去重和源 PTS 起点尚未校准。
- 片段成本只由外部 Provider 回报，尚未接入账目、估算和未知扣费策略。

这些不确定项不能由合成时长或文本通过而提前开放转录目标。
