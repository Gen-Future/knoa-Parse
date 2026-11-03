# M3-I Azure 文档分析适配器基础执行记录

日期：2026-11-04；环境：Windows，仓库 `.venv` CPython 3.12.13。需求：[M3-I before](../changes/2026-11-04-m3i-azure-adapter-before.md)；不确定项：[M3-I after](../changes/2026-11-04-m3i-azure-adapter-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_azure_document_analysis.py -v` | 11 项通过：提交/轮询、映射、空页、错误、超时、重定向、资源限制和结构拒绝 |
| 真实 Azure 请求 | 未执行；没有账户凭据，避免把合成服务当作真实效果证明 |
| worker/API/console 注册 | 未注册；能力仍只开放六种 `native_extract` 后缀 |
| 新增依赖 | 0；使用标准库 `urllib`、`json`、`base64` |
| 原始响应/账目持久化 | 未实现；保留到后续产品接入阶段 |

离线测试只证明 adapter 的传输与契约边界，不证明服务可用性、费用、区域合规、OCR 效果、表格理解或生产恢复能力。
