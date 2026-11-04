# M4 开发完成审计

日期：2026-11-04，最终复核：2026-11-05；审计对象：M4 音频与视频代码阶段。这个审计把实现证据与生产开放闸门分开，不能用合成服务结果代替真实 ASR 效果。

## 已完成的代码范围

- 媒体流、time base、VFR 实际 PTS、源摘要和受控 ffprobe；M4-I 修复了 staged source、负 PTS 和 bounded subprocess 边界。
- PySceneDetect 0.7.2 headless optional extra、Content/Adaptive detector adapter、场景覆盖和时间关联。
- FFmpeg 受限音频裁剪、重叠 chunk/core 区间、SRT/WebVTT、无音轨和缺段语义。
- 供应商无关 ASR、Azure Speech 2025-10-15 multipart adapter、词级时间/speaker 偏移映射。
- 转录编排、partial/failed coverage、unknown/not_sent/known 费用状态；结果保持独立，不写旧 ParseResult。

## 当前证据

| 检查 | 结果 |
| --- | --- |
| `scripts/check.py` | 通过，299 个仓库文件 |
| `uv lock --check` | 锁定环境此前通过，video extra 已锁定；本机未安装 `uv`，本轮无法重跑 |
| `scripts/audit_dependencies.py --documents --api --video` | 通过，69 条 lock 记录，无禁止依赖 |
| `python -m unittest discover -s tests -v` | 224 项通过，2 项 optional toolchain 在当前受限 Windows 路径环境中安全跳过 |
| 设置 FFmpeg/ffprobe 路径后的 optional toolchain | 2 项通过：真实音视频生成、ffprobe PTS、PySceneDetect 场景、FFmpeg WAV 裁剪 |
| Azure Speech 适配器专项 | 3 项通过；使用本地合成 HTTP，无真实账户调用 |

## 未开放的生产闸门

- Azure Speech 区域、权限、中文/噪声/静音/重叠讲话效果、价格、账单和数据保留尚未真实验证。
- 真实长 VFR、损坏容器、跨平台 FFmpeg 构建/许可证、字幕容器抽取和编码延迟尚未验收。
- ProviderInvocation/Coordinator 已有 media runner/worker 装配入口；真正的 worker/API/console job 路由、query/cancel、跨进程崩溃恢复和新 `transcribe`/`video_understanding` 结果契约尚未接入。

因此 M4 的代码开发阶段完成，生产能力仍由 [TODO](../../docs/TODO.md) 的真实服务闸门控制。
