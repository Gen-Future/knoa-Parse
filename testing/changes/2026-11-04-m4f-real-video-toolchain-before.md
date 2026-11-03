# 开发前测试需求：M4-F 真实本地视频工具链验收

创建日期：2026-11-04；状态：实现前定义。范围：锁定可选 `video` 依赖中的 PySceneDetect headless 版本，并在 Windows 上使用外部 FFmpeg/ffprobe 对合成 MP4 做真实流、PTS、覆盖和场景检测验收；不发送 ASR 请求，不安装任何本地模型。

## 目标与边界

- `video` extra 只包含 `scenedetect-headless==0.7.2` 及其非模型依赖，默认安装不引入 OpenCV；uv.lock 必须同步，依赖审计必须通过。
- FFmpeg/ffprobe 由运行环境提供，版本和路径不写入仓库；本阶段验证受控 `ffprobe` adapter 能读取真实 MP4，不能把系统安装当作跨平台发布保证。
- PySceneDetect 使用已审计的 OpenCV backend，Adapter 只映射官方 `FrameTimecode` 到毫秒和帧范围；不调用 `split_video_ffmpeg`，不复制 detector 源码，不声明视觉理解。
- 合成 MP4 必须包含明确的场景变化；用真实帧 PTS 验证时序、场景覆盖和源摘要保护。

## 验收用例

- [ ] M4F-01 / P0：`uv.lock` 记录 video extra、PySceneDetect 0.7.2、OpenCV headless 及非模型传递依赖；依赖审计无禁止包。
- [ ] M4F-02 / P0：真实 ffprobe 解析合成 MP4，duration=2000ms、20 帧，前 3 个 PTS 为 0/100/200ms。
- [ ] M4F-03 / P0：真实 PySceneDetect ContentDetector 将白/黑两段映射为 [0,1000)、[1000,2000)，覆盖完整。
- [ ] M4F-04 / P0：未安装 video extra 时返回稳定 dependency_missing；真实工具错误和源摘要变化不泄漏 stderr/原文。
- [ ] M4F-05 / P0：专项、完整回归、`scripts/check.py`、`uv lock --check` 和依赖审计通过。

真实摄像机 VFR、长视频、损坏容器、跨平台 FFmpeg 构建/许可证和外部 ASR 账户效果仍属于后续人工/真实服务验收。
