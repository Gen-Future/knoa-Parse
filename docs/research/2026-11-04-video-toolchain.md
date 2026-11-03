# M4-F 视频工具链选择与真实验收

PySceneDetect 0.7.2 是当前锁定版本。官方文档说明 0.7 的 `FrameTimecode` 在 VFR 场景中以 time base 为权威，`detect()` 返回 start/end timecode；headless 分发提供服务器环境所需的 OpenCV headless 依赖。[官方 API](https://www.scenedetect.com/docs/latest/api.html) [官方 V0.7 说明](https://www.scenedetect.com/docs/latest/api/common.html) [官方 0.7.2 发布页](https://github.com/Breakthrough/PySceneDetect/releases)

Knoa 只接入 PySceneDetect 的公开 detector/API，不复制源码，不使用 `split_video_ffmpeg` 编辑层。当前 adapter 固定 OpenCV backend，把 FrameTimecode 映射为 Knoa 的毫秒和帧范围，场景仍是候选结果；视觉理解、OCR、ASR 通过独立 Provider。

项目将 PySceneDetect 放在可选 `video` extra，默认安装保持轻量。FFmpeg/ffprobe 是外部运行时，不打包进仓库；adapter 使用参数数组、源摘要前后校验和稳定错误码。真实 Windows 验收使用 FFmpeg/ffprobe 9.0.2 和合成 MP4，完整记录见 [M4-F](../../testing/records/2026-11-04-m4f-real-video-toolchain.md)。
