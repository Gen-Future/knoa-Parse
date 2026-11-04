# 开发后不确定项：M4-I 媒体边界缺陷修复

日期：2026-11-04；对应需求：[M4-I before](2026-11-04-m4i-media-defect-fixes-before.md)。

## 已验证

- core media identity 不再携带路径；StagedMedia 统一承载受信任文件边界。
- 负 PTS/stream 起点可进入内部 timeline，音频 chunk 记录 timeline origin，FFmpeg 使用文件相对 offset。
- bounded subprocess reader 在 stdout 超限时终止进程，覆盖 ffprobe/FFmpeg。
- runner 有总 deadline、取消检查、发送后取消和重叠段去重；frame scan 必须指定 stream。
- artifact/source/header/worker 白名单边界已测试。

## 仍需真实环境确认

- worker 中真正执行媒体目标仍需独立 media job 路由和 ProviderInvocation 持久化；本阶段修复只解决边界，不开放产品目标。
- 多轨不同 start time、负 PTS 的真实容器组合仍需去敏样本验收。
