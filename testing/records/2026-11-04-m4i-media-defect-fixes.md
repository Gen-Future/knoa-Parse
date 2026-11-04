# M4-I 媒体边界缺陷修复执行记录

日期：2026-11-04；环境：Windows，Python 3.12.13。

| 检查 | 结果 |
| --- | --- |
| 媒体/ASR/场景/runner 专项 | 通过 |
| `scripts/check.py` | 通过 |
| worker subprocess guard | 通过：仅允许 ffmpeg/ffprobe |
| 真实本地工具链 | 通过：ffprobe、PySceneDetect、FFmpeg WAV 裁剪 |
| 真实 Azure ASR / 产品路由 | 未执行/未开放 |
