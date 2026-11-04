# 开发后不确定项：M4-K 容器字幕提取

日期：2026-11-04；对应需求：[M4-K before](2026-11-04-m4k-subtitle-extraction-before.md)。

- 已新增 bounded FFmpeg subtitle extractor，并将输出交给 WebVTT 解析器。
- 当前测试使用合成 FFmpeg 输出；真实多字幕轨、ASS/SSA 样式、编码和时间偏移仍需真实媒体验收。
