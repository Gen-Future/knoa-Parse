# 开发前测试需求：M3-B 通用外部文档服务适配器

创建日期：2026-10-22；状态：实现前定义。范围：无供应商绑定的同步 HTTP 文档分析适配器及本地合成服务测试。不开放 OCR/document_understanding 产品目标，不接入 worker/API，不改变 0.2 结果契约或能力清单。

## 目标与边界

适配器将内部 `PageRequest` 映射为受控 JSON 请求，将服务响应严格校验为 `PageAnalysis`。服务收到的是已准备的页图字节和明确的同页上下文；适配器不渲染 PDF、不识别图片、不计算来源定位、不自动重试，不跟随重定向，不把供应商异常原文写入报告。

默认只允许 HTTPS；仅测试配置允许回环 HTTP。API key 只用于 Authorization 头，不能出现在 URL、异常、日志、`describe()` 或序列化报告。响应按字节上限读取，错误状态映射为稳定代码和 retryable 标记。

## 协议预期

请求：`POST {base_url}/analyze/page`，JSON 包含 `page`、`width_px`、`height_px`、`width_pt`、`height_pt`、`image_base64`、`context`、`trace_id`；不发送源文件路径或其他页。响应：`page`、`model`、`elements[]`（kind/text/bbox/unit/origin），可选 `blank`、`total_tokens`。响应中的页面、坐标和元素仍由编排层做最终校验。

## 验收用例

- [ ] M3B-01 / P0：合法 HTTPS 配置生成正确端点、JSON 字段和 Bearer 头；不泄露源路径、其他页或 key。
- [ ] M3B-02 / P0：默认拒绝 HTTP、缺少/非法 HTTPS URL、空 key、无效超时与响应上限；回环 HTTP 仅测试显式开启。
- [ ] M3B-03 / P0：401/403/402/404/408/429/5xx 映射稳定错误；429/408/5xx retryable，其他永久错误不重试；响应正文不回显。
- [ ] M3B-04 / P0：服务 3xx 不自动跟随；重定向目标不能收到 key；重定向响应归为稳定错误。
- [ ] M3B-05 / P0：Content-Length 或实际响应超过上限时有界失败；无效 JSON、错误顶层类型、缺字段、超长文本、非法坐标均不发布。
- [ ] M3B-06 / P0：服务返回错误 page、未声明坐标单位、空元素但未显式 blank、非有限数字时严格失败；不能由适配器猜测修复。
- [ ] M3B-07 / P1：请求超时、连接失败、远端断开映射为 retryable provider 错误；一次调用只发送一次，不自动重试。
- [ ] M3B-08 / P1：`describe()` 只返回非敏感 capability；key 不出现在 repr、异常、响应对象或诊断 JSON。
- [ ] M3B-09 / P0：接入 M3-A 编排时 partial/failed、调用账目、total_tokens=null/0 语义保持；适配器不将响应直接提升为 ParseResult。
- [ ] M3B-10 / P0：全量回归、源码边界、依赖审计通过；不新增运行依赖，能力清单仍不出现 OCR/document_understanding。

自动测试使用本地 HTTPServer，仅验证协议和传输安全，不代表任何真实厂商效果、OCR 准确率、费用或服务 SLA。人工/真实服务验证转入开发后 TODO。

通过条件：所有适用自动项通过；HTTP 适配器只作为显式注入组件存在，未注册到产品路由。开发后记录：[M3-B 不确定项](2026-10-22-m3b-http-provider-after.md)。

## 2026-11-02 收尾前补充要求

上次仅执行局部测试，本次先明确剩余预期再修正：配置 repr 隐藏密钥；禁止 URL 内凭据、非法端口和控制字符；请求/响应均有字节上限；响应 JSON 拒绝重复键和非标准数值；读失败/HTTP 错误/重定向及时释放连接。统一 core ProviderError，使错误进入 M3-A 账目时保留稳定代码及 retryable。增加真实回环 HTTP 与编排联动测试，证明第二页错误不覆盖第一页、无重试、未知用量不填零；确认完整环境与无文档环境均能运行。请求增加 media_type，避免服务猜测图片类型。真实服务、OCR 效果和远端计费保持未验收，并集中记录到 docs/TODO.md。
