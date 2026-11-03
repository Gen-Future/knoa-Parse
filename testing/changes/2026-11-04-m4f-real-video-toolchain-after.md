# 开发后不确定项：M4-F 真实本地视频工具链验收

日期：2026-11-04；对应需求：[M4-F before](2026-11-04-m4f-real-video-toolchain-before.md)。

## 已验证

- `video` extra 已锁定 `scenedetect-headless==0.7.2`；uv lock 解析 69 条记录，video 依赖审计通过，无本地模型或禁止包。
- Windows 使用 FFmpeg/ffprobe 9.0.2 真实二进制解析合成 MP4，得到 2000ms、20 帧和 0/100/200ms PTS。
- PySceneDetect 0.7.2 ContentDetector 真实处理同一 MP4，输出两段场景并覆盖完整时间线；源摘要在处理前后保持一致。

## 仍需人工或真实环境确认

- 当前验证使用合成 CFR MP4；真实 VFR、B 帧、负 PTS、音视频不同起点、字幕容器和损坏文件仍未验收。
- FFmpeg 9.0.2 来自本机 winget，仓库只锁定 Python adapter/extra，不打包或声明系统二进制安装器；Linux/macOS/容器路径和许可证构建选项需另行确认。
- 没有真实 ASR 服务、去敏语音集、账单和外部缺段证据，`transcribe`/`video_understanding` 仍未开放。

这次真实工具验收提升了 M4 本地媒体基础的证据强度，但不替代服务效果验收。
