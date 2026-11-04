# 开发前测试需求：M4-I 媒体边界缺陷修复

创建日期：2026-11-04；范围：修复审计发现的媒体路径、时间线、资源、取消和边界去重缺陷；不开放真实 ASR，不接入旧 ParseResult。

## 验收目标

- core 只保存 source identity；磁盘路径通过 processor 的 `StagedMedia` 注入。
- chunk、scene、ASR 内部时间保留 stream 起点和负 PTS；音频提取换算为文件相对时间。
- ffprobe/FFmpeg stdout 超过上限时立即终止，不先积累无限内存。
- 转录 runner 使用总 deadline、取消回调，并对重叠 chunk 的重复段做稳定边界去重。
- worker audit hook 允许受控 ffmpeg/ffprobe，拒绝其他子进程。
- source ID、artifact SHA、ASR header 控制字符和 frame stream selector 都在边界校验。

## 验收用例

- [ ] M4I-01：core media input 序列化没有 path；StagedMedia 才能执行媒体工具。
- [ ] M4I-02：负 stream 起点生成负 source timeline，chunk core 连续，提取命令换算为非负输入偏移。
- [ ] M4I-03：无 stream selector 的 frame probe 被拒绝；stdout overflow/timeout 稳定失败且不产生未关闭管道。
- [ ] M4I-04：取消在发送后保留失败/unknown 语义，剩余 chunk 不发送；重叠 transcript 不重复。
- [ ] M4I-05：artifact SHA、source ID、header 控制字符和 worker 子进程白名单有测试。
- [ ] M4I-06：完整回归、静态检查、真实本地 FFmpeg/PySceneDetect 验收通过。
