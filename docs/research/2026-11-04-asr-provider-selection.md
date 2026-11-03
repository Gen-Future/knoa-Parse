# M4-G 外部 ASR 选型与 Azure Speech 适配边界

首个候选选择 Azure Speech fast transcription REST API 2025-10-15。官方文档给出同步 multipart 接口、250MB/2小时文件限制、`Ocp-Apim-Subscription-Key` header 和 `phrases`/`words` 的毫秒 offset/duration；功能表包含指定 locale、词级时间和 diarization。[官方 REST reference](https://learn.microsoft.com/en-us/rest/api/speechtotext/transcriptions/transcribe?view=rest-speechtotext-2025-10-15) [官方 fast transcription 指南](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/fast-transcription-create)

选择依据：接口与已完成的单片段 `AsrProvider` 直接对应；可上传受控字节而不要求外部 URL；响应有词级时间和 speaker；官方 API 版本当前明确为 2025-10-15。实现位于 `providers/asr/azure_speech.py`，不把 Azure JSON 直接暴露给公共结果。

接入边界保持四层：FFmpeg 负责音频准备，Knoa chunk planner 管理上限和 core 去重，Azure adapter 负责协议/偏移映射，coverage/ledger 负责缺段和费用未知。真实账户验证前不注册产品能力；不安装 Whisper、faster-whisper、神经 VAD 或本地权重。
