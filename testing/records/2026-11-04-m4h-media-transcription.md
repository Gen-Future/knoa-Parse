# M4-H 音频执行编排执行记录

日期：2026-11-04；环境：Windows，Python 3.12.13，FFmpeg/ffprobe 9.0.2。需求：[M4-H before](../changes/2026-11-04-m4h-media-transcription-before.md)；不确定项：[M4-H after](../changes/2026-11-04-m4h-media-transcription-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_media_transcription.py -v` | 2 项通过：部分 chunk、unknown cost、无音轨前置 |
| `python -m unittest discover -s tests -p test_optional_video_toolchain.py -v` | 2 项通过：真实 FFmpeg 音频裁剪、ffprobe PTS、PySceneDetect 场景 |
| 真实 Azure Speech | 未执行；使用合成 Provider/本地 HTTP，避免计费调用 |
| 产品路由/ParseResult | 未修改，`transcribe` 仍未开放 |

自动测试证明本地媒体执行与编排边界，不证明真实 ASR 效果、费用或生产恢复。
