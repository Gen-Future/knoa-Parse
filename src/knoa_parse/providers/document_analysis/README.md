# 外部文档分析服务适配

状态：core/document_analysis.py 已定义同步单页内部协议，enrichment/document.py 提供独立页级编排；http.py 提供不绑定厂商的 HTTPS/受控 JSON transport。尚无真实供应商实现或凭据，不开放产品目标。合成 Provider 只位于 evals，不进入本目录或产品能力清单；见 [M3-A](../../../../docs/m3-document-analysis.md) 和 [M3-B](../../../../testing/changes/2026-10-22-m3b-http-provider-after.md)。

文档或页图 → 块、表格、页面区域与阅读顺序。

可由一次调用覆盖 OCR/布局/表格；调用计划避免同时重复跑独立 OCR。

只依赖 core 的 Provider 接口及选定外部服务客户端；具体供应商后续在本目录内增加适配器，不创建供应商专用资料流程。连接外部受管服务，禁止本地模型加载、权重下载和隐式本地回退。

请求、异步任务、能力声明、费用预算、错误和坐标/时间归一化按 [接口草案](../../../../docs/provider-interfaces.md) 实现。缺少服务应报告能力缺失，不用 mock 产物声称解析成功。
