# 媒体工具

状态：M4-A 已实现受控 ffprobe 探测边界，M4-C 已实现不含解码器的 PTS 场景候选和区间关联，M4-D 已实现受限音频 chunk 与 SRT/WebVTT 时间线；尚未安装/锁定真实二进制或 PySceneDetect，也未启用音视频产品路由。

音视频探测、转码、音轨提取、规则抽帧，以及图像尺寸/方向处理。候选为 FFmpeg/ffprobe 和所选语言的图片解码库。

`core/media.py` 定义流信息、时间基和实际 PTS 模型；`ffprobe.py` 通过注入的外部进程返回流/帧元数据；`scenes.py` 只根据注入样本生成候选和时间链接；`timeline.py` 规划受限音频 chunk 并解析 SRT/WebVTT。转码、派生产物、OCR、ASR、神经 VAD 和语义抽帧模型仍不在本阶段。

只依赖 core 接口及审核后的非模型工具。由 apps 注入解析流程；不得调用 providers 或加载推理模型。CPU/GPU 计算本身不是判断标准，是否包含学习模型及权重才是边界。

详细来源见 [调研](../../../../docs/research/2026-10-14-parser-landscape.md)。安装时锁定版本并验证二进制、传递依赖、退出码、资源限制和首次运行行为。
