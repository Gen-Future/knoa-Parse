# M4-G Azure Speech 外部 ASR 适配器执行记录

日期：2026-11-04；环境：Windows，Python 3.12.13。需求：[M4-G before](../changes/2026-11-04-m4g-azure-speech-before.md)；不确定项：[M4-G after](../changes/2026-11-04-m4g-azure-speech-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_azure_speech_asr.py -v` | 3 项通过：multipart/definition、绝对偏移、配置/错误/越界词 |
| 官方协议 | 选定 REST API 2025-10-15；无 SDK、无本地模型 |
| 真实 Azure 请求 | 未执行；没有账户凭据，避免产生计费调用 |
| 产品路由/能力清单 | 未注册，`transcribe` 仍未开放 |

自动测试证明协议映射和失败边界，不证明真实服务准确率、费用、区域或 SLA。
