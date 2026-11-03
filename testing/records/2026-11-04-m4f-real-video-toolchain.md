# M4-F 真实本地视频工具链验收记录

日期：2026-11-04；环境：Windows，Python 3.12.13，FFmpeg/ffprobe 9.0.2（winget），PySceneDetect 0.7.2（`video` extra）。需求：[M4-F before](../changes/2026-11-04-m4f-real-video-toolchain-before.md)；不确定项：[M4-F after](../changes/2026-11-04-m4f-real-video-toolchain-after.md)。

| 检查 | 结果 |
| --- | --- |
| `uv lock --check` | 通过 |
| `python scripts/audit_dependencies.py --video` | 通过：69 条 lock 记录，无禁止依赖 |
| `python -m unittest discover -s tests -p test_optional_video_toolchain.py -v` | 1 项通过：真实 ffprobe + PySceneDetect 合成 MP4 验收 |
| 真实媒体事实 | duration 2000ms，20 帧，PTS 0/100/200ms；场景 [0,1000)、[1000,2000)；覆盖 2000ms |
| 真实 ASR/长 VFR/跨平台 | 未执行 |

合成 MP4 由测试现场生成，未提交媒体或二进制。该记录证明本机工具链和 adapter 可运行，不证明所有格式或外部服务效果。
