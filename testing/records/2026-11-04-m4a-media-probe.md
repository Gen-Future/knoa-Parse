# M4-A 音视频媒体探测边界执行记录

日期：2026-11-04；环境：Windows，仓库 `.venv` CPython 3.12.13。需求：[M4-A before](../changes/2026-11-04-m4a-media-probe-before.md)；不确定项：[M4-A after](../changes/2026-11-04-m4a-media-probe-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_ffprobe_media.py -v` | 7 项通过：流映射、VFR PTS、源身份、工具错误、输出/帧限制和非法响应 |
| 真实 ffprobe/媒体文件 | 未执行；测试使用显式合成 JSON 和临时源字节，不证明编解码器或真实时间线效果 |
| ASR/OCR/场景检测/转码 | 未实现 |
| 新增依赖 | 0；使用标准库 subprocess、json、hashlib、decimal |
| 产品能力清单 | 未改变，音频/视频仍未启用 |

自动测试只证明进程边界和数据契约，不证明 FFmpeg 构建、许可证、格式覆盖、VFR 实际 PTS 或媒体效果。
