# 开发前测试需求：M4-G Azure Speech 外部 ASR 适配器

创建日期：2026-11-04；状态：实现前定义。范围：选择 Azure Speech fast transcription REST API 2025-10-15 作为首个外部 ASR 候选并接入现有 `AsrProvider`，验证 multipart 音频、definition、词级时间、speaker 和片段偏移；不发送真实账户请求，不安装本地模型，不开放 `transcribe`。

## 目标与边界

- 使用官方同步 `POST /speechtotext/transcriptions:transcribe?api-version=2025-10-15`，API key 仅放 `Ocp-Apim-Subscription-Key`，不引入 Azure SDK。
- 只发送已校验的派生音频片段；请求字段采用 `locales`、`wordLevelTimestampsEnabled` 和可选 `diarization.enabled`，供应商相对毫秒时间加片段起点。
- 只映射 `phrases`/`words` 到独立 `AsrResponse`；供应商置信度、combinedPhrases 和账单原文不进入旧 ParseResult。费用未知保持 null。
- 严格拒绝重定向、越界时间、错误媒体、过大请求、非法 JSON 和供应商错误正文；adapter 未注册 worker/API/catalog。

## 验收用例

- [ ] M4G-01 / P0：multipart path/version/key、definition 和音频字节正确；source ID 与 key 不出现在 body/结果。
- [ ] M4G-02 / P0：phrase/word offset + duration 映射到源时间线，speaker 保留；空 phrases 可表示静音片段。
- [ ] M4G-03 / P0：媒体/摘要/大小/时长/版本配置和 request limit 在外发前校验。
- [ ] M4G-04 / P0：401/403/408/429/5xx、超时、非法 JSON、重定向和越界词归一化为稳定错误，不泄漏供应商正文。
- [ ] M4G-05 / P0：专项、完整回归、静态检查和 video/默认依赖审计通过；不新增本地模型。

真实 Azure Speech 区域、中文效果、价格、数据保留、长音频、静音、重叠讲话、说话人和账单核对留在后续人工/账户验收。
