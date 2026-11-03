# 视频解析

状态：planned；M4-A/M4-C/M4-F 完成可注入 ffprobe、PySceneDetect 场景候选和真实合成 MP4 基础验收，视频解析仍未实现/启用。建议优先级：P1。属于资料家族，后续可以是同一个进程中的模块，不要求独立服务。

## 范围

首批候选：`.mp4`、`.mov`、`.mkv`、`.webm`。后续候选：`.avi`。这些是规划，不是支持声明。

## 专用流程

媒体探测 → 音轨子任务/字幕/规则抽帧 → 外部模型 → 三路原时间线对齐 → 覆盖记录。

## 定位与输出

stream ID、原始 PTS/timebase、毫秒范围、帧图区域与派生关系。

现有 v0.1.0-draft.1 不一定能表达本家族全部结构，按 [结果模型](../../../../docs/result-model.md) 升级契约后再开放相应能力。

## 依赖边界

只依赖 core 定义的接口，apps 注入成熟转换/内容增强适配、非模型工具和外部 Provider；仅按当前家族需要使用。非模型工具分组：media。按目标可能需要的外部能力：asr、ocr、vision；不是每个文件都全部调用。不得导入其他家族内部代码；复合资料走 core 子任务分派。

## 复用候选

直接采用 PySceneDetect 的 AdaptiveDetector/ContentDetector 和 FFmpeg/ffprobe，排除 RAG-Anything 视频处理器及 MoviePy。分镜结果是候选；以实际 PTS 校验时间映射，视觉/ASR 走外部接口，字幕与转录独立保留。headless 依赖仅在视频阶段加入。 具体边界见 [横向选型](../../../../docs/research/2026-10-15-module-selection.md) 和 [实现方案](../../../../docs/implementation-plan.md)；当前未安装或启用。

## 实现前验收

无音轨、字幕不匹配、可变帧率、镜头很短、画面/声音矛盾；只转录模式不能声称完成音画理解。

共同规则见 [处理流程](../../../../docs/pipelines.md) 与 [评测计划](../../../../evals/README.md)。
