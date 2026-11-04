# 媒体工具

状态：M4-A～E 已实现基础边界，M4-F 已锁定可选 `scenedetect-headless==0.7.2` 并完成 Windows 真实合成 MP4 验收，M4-H 已完成真实 FFmpeg chunk 裁剪与转录编排；FFmpeg/ffprobe 仍由运行环境提供，音视频产品路由未启用。

音视频探测、转码、音轨提取、规则抽帧，以及图像尺寸/方向处理。候选为 FFmpeg/ffprobe 和所选语言的图片解码库。

`core/media.py` 定义流信息、时间基和实际 PTS 模型；`ffprobe.py` 通过注入的外部进程返回流/帧元数据；`scenes.py` 只根据注入样本生成候选和时间链接；`timeline.py` 规划受限音频 chunk 并解析 SRT/WebVTT；`ffmpeg.py` 执行受限音频裁剪并连接外部 ASR；`subtitles.py` 提取容器字幕；`coverage.py` 汇总无音轨、缺段和未知费用。派生产物、OCR、神经 VAD 和语义抽帧模型仍不在本阶段。

只依赖 core 接口及审核后的非模型工具。由 apps 注入解析流程；不得调用 providers 或加载推理模型。CPU/GPU 计算本身不是判断标准，是否包含学习模型及权重才是边界。

详细来源见 [调研](../../../../docs/research/2026-10-14-parser-landscape.md) 和 [M4-F 工具链调查](../../../../docs/research/2026-11-04-video-toolchain.md)。安装时锁定版本并验证二进制、传递依赖、退出码、资源限制和首次运行行为。
