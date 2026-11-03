# M3-B 通用外部文档服务适配器执行记录

日期：2026-10-22；环境：Windows，仓库 .venv CPython 3.12.13；使用本机回环 HTTPServer 合成服务，无真实凭据、无外网、无模型调用。需求：[M3-B 开发前需求](../changes/2026-10-22-m3b-http-provider-before.md)；后续 TODO：[M3-B 开发后不确定项](../changes/2026-10-22-m3b-http-provider-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_document_analysis_http.py -v` | 9 项通过；覆盖请求映射、认证头、默认 HTTPS、状态映射、重定向、响应上限、非法响应、网络失败及 M3-A partial 联动 |
| 真实供应商调用 | 未执行；不得据此声明 OCR/document_understanding 可用 |
| 真实页图/几何 | 未执行；适配器仍要求上游提供 full_page_upright 页图 |
| 新增依赖 | 0；使用 Python 标准库 urllib |
| 完整 Python 回归 | 119 项通过（2026-11-02 收尾复验） |
| 产品能力 | 未注册；`capabilities` 仍仅开放六种 `native_extract` 及已有 text_model |

已验证：响应正文和供应商错误不会进入公开异常，key 不进入 capability/URL/报告，重定向不跟随，超大响应有界停止，单次调用不会自动重试。测试中的 `synthetic-secret` 只存在内存和本地合成请求，未写入文件。

人工验证和真实服务 TODO 见 after 文档；本记录不勾选真实 OCR 相关项目。
