# M3-A：外部文档页级编排基础

状态：内部协议和离线编排可验证，尚未选择/接入真实 OCR 或文档分析服务。新代码不在 native worker、API 或 UI 产品路由中，运行能力仍只有 native_extract；这不是扫描资料已可识别的声明。

开发前目标见 [测试需求](../testing/changes/2026-10-19-m3-foundation-before.md)，人工验证见 [开发后不确定项](../testing/changes/2026-10-19-m3-foundation-after.md)。

## 模块与输入

- core/document_analysis.py：DocumentAnalysisProvider、DocumentCapability、PreparedPage、PageRequest、PageAnalysis。只定义同步单页协议，不引入 SDK。
- enrichment/document.py：analyze_pages、select_context、预算及独立实验报告。不依赖具体 Provider 或引擎。
- evals/m3_fixtures.py：ScriptedDocumentProvider，明确标记 mock，只返回预写文字/坐标和失败，不读取图片或推理，不进入产品 Provider 注册表。

输入为既有 PDF 原生 ParseResult 与调用方准备的完整正向页图。页图绑定 Source ID、SHA、原件 artifact ID、页号及派生 artifact，字节摘要/大小必须匹配。页号须存在于原生 coverage 的 page-N 中，重复页/重复 artifact/错误类型/超预算在任何外发之前拒绝。

M3-C 的 `processors/pdf/page_inputs.py` 负责这组前置绑定和 0/90/180/270 度 upright 宽高检查，并允许 2% 栅格取整比例误差。它不负责 PDF 渲染；真实渲染与旋转/裁切效果仍需人工验收。

M3-D 的 `processors/pdf/rendering.py` 定义 `PdfRenderer`、`PdfRenderRequest` 和 `RenderBudget`。它先核对固定 Source 字节，再将排序后的页规格与预算交给显式注入的 Renderer，最后把所有输出一次性送入 M3-C；没有实际渲染器、路径访问或强制进程超时。

M3-E 的 `core/provider_runs.py` 定义调用账目、远端引用、用量和 `decide_recovery()`。它只返回 submit/retry/query/manual/skip 等决策，不调用 Provider、不写数据库；unknown billing 默认不能自动重试。SQLite、worker 恢复和真实远端能力需另建产品接入阶段。

M3-F 将 `InvocationRecord` 持久化到 Store 的 `provider_invocations` 表，并用 `schema_meta` 标记 schema 版本 2。写入使用 `(run_id, unit_id)` 唯一约束、expected-state 检查和 SQLite 事务；read-only Store 只能查询。该表尚未由 worker 创建或更新，也不通过 API 暴露。

这里不渲染 PDF，不验证图片解码尺寸与原 PDF 页框的一致性，不处理裁切/旋转/EXIF。尺寸与 full_page_upright 映射由可信调用方负责。正式接入前需要真实页图准备与几何校验，不可直接把网络用户提供的尺寸当权威来源。合成 fixture 的字节不是实际 PDF/页图，只证明编排语义。

## 合并、定位与上下文

按源页号排序输出。px 或 normalized 坐标按声明原点换算到原件 pt/top_left；非有限、反向、空框、越界、未声明单位和错误页响应拒绝整页，不发布同页的半份结果。当前定位精度保守为 estimated；真实服务校准之前不承诺 source_exact。

OCR 文字 acquisition=ocr，视觉描述 acquisition=inferred。新块保留输入页及同页原生上下文 ID；上下文按原生保留顺序选取，只接受所有定位都属于同一源页的 native 文本块，跨页归属不明的块不发送。限制字符数与块数，部分文本有 truncated 标记，账目保存实际发出的上下文引用及文本。

返回独立 AnalysisReport：pages 输入引用、outcomes、外部 blocks、invocations 与用量。它不是 ParseResult，也不混入原生 blocks 或修补原生 coverage；同页原生页眉与 OCR 可能重复，后续产品集成必须明确去重/并置规则。context_block_ids 引用输入的原生结果，消费内部报告时需同时保留原生结果。

空页必须由 Provider 显式 blank=true；空列表不是默认成功。某页失败后仍可处理其他页，不重试；全部所选页 completed 才是本次实验 completed，至少一页 completed 且有失败为 partial，否则 failed。即使所有页为空白而无块，逐页结果仍清楚可见。这只描述所选页分析，不保证整个文档、表格或阅读顺序目标完成。

## 调用与预算

限制页数、输入总字节、每页字节/像素、调用数、总时限、输出块/文字数及每页上下文。发送前整批预检输入；调用预算不足的后续页 not_sent，不隐式拆更多请求。超输出预算丢弃该页全部新块，不悄悄截断为成功。

同步调用前后检查取消/单调时钟，并传入剩余 timeout_seconds。取消和超时不能强制停止未遵守超时的适配器，不能保证远端停止计费；返回内容会被丢弃，发送过的 invocation 留存。远端异常或非法响应的结算状态可能 unknown，无自动重试/回退。仅允许稳定白名单错误代码，其他错误归一化，不写供应商异常原文。

total_tokens 来自供应商，任何已发送调用未知则聚合值为 null；显式 0 保留。cost 始终 null，没有实现货币预算或估价，不同供应商 token 不提供统一成本承诺。

mock 必须显式 dry_run=true，否则外发前拒绝。报告和每次调用标明 mock；正式 worker/API 不会选到这个 mock。报告 JSON 不序列化页图 bytes 或凭据；原生上下文、OCR 文字仍是资料，报告应存私密目录。

## 本地离线验收

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_document_analysis.py -v
.\.venv\Scripts\python.exe scripts/evaluate_m3.py
```

演示报告在 `.local/m3-dry-run/report.json`，预期第 1 页成功、第 2 页合成超时，整体 partial、2 次调用、未知总用量。脚本退出 0 只表示编排断言通过，不表示真实服务通过。

## 后续产品接入

通用 HTTP transport 已作为独立适配器骨架实现于 `providers/document_analysis/http.py`，协议测试使用本地合成服务；它不属于产品能力。真实服务选型、页图、效果、费用与恢复的待办见 [M3-B after](../testing/changes/2026-10-22-m3b-http-provider-after.md)。

1. 选择一个满足需求的外部服务，调查传输、区域/资料边界、精确定位、模型版本、限额、异步/幂等/取消与计费方式。不能把已有文本模型协议直接宣称为 OCR。
2. 实现并验收全页渲染和来源几何映射，保存页图、实际服务原始响应与必要派生关系。
3. 定义 document_understanding 的新版结果契约、调用账目持久化、页级恢复和原生/识别覆盖合并；通过真实效果与成本验收后再开放任务目标。

本轮不修改既有 0.2 契约、主仓旧快照、uv.lock 或格式 catalog，不新增依赖，不发送真实账户请求。M2 真实中文资料验收继续独立进行。
