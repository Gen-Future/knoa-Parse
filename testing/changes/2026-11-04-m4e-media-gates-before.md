# 开发前测试需求：M4-E 音视频覆盖与成本闸门

创建日期：2026-11-04；状态：实现前定义。范围：统一音视频目标的无音轨前置检查、chunk 完成/缺段覆盖、转录/视频目标状态和费用未知语义；不接真实 Provider、不写 ParseResult、不宣称效果。

## 目标与边界

- `transcribe` 必须先找到音轨；无音轨、无有限 duration 或没有可发送 chunk 时明确 failed，不能用视觉或空转录掩盖声音目标缺失。
- 每个 chunk 只以不重叠的 `core` 区间计入覆盖；所有 core 完成且请求范围无缺段才是 completed；至少一个成功且有缺段为 partial；全部未完成为 failed。
- 失败 chunk 必须带稳定 issue code 并输出 missing ranges；结果保留已完成区间，不把 provider 缺段当成静音。
- 费用状态分为 `not_sent`、`known`、`unknown`；任一已发调用费用未知时总费用为 null，禁止写 0；所有已发调用的 usage 由调用方提供。
- `video_understanding` 仍需要视觉/音频/字幕目标分别验收；本闸门只做时间/覆盖/成本摘要，不开放目标。

## 验收用例

- [ ] M4E-01 / P0：有音轨返回 stream index；无音轨稳定返回 `media_audio_required`。
- [ ] M4E-02 / P0：连续完成 chunk 的 core 区间得到 completed、零 missing ranges；成本已知时求和并保留显式 0。
- [ ] M4E-03 / P0：失败 chunk 形成 missing range，已有结果保留为 partial；不把失败区间算作 covered。
- [ ] M4E-04 / P0：没有发送/没有完成 chunk 为 failed，billing=`not_sent`、cost=null。
- [ ] M4E-05 / P0：任一 usage cost=null 时 billing=`unknown`、cost=null；重复/重叠 chunk、非法 target 和不带失败码的失败 outcome 拒绝。
- [ ] M4E-06 / P0：专项、完整回归、静态检查、依赖审计和文档检查通过；不新增模型/外部依赖。

真实服务账单核对、费用估算、跨供应商货币、失败重试、转录质量和视频音画完整性留在产品接入验收。
