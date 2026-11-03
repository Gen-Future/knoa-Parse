# Knoa Parse 待办与能力闸门

更新日期：2026-11-04。这里记录尚未完成、不能从自动测试推断完成、或必须经过人工/真实服务验收后才能开放的事项。勾选代码测试不等于解除能力闸门；每项开放前必须补开发前需求、执行记录和开发后不确定项。

## 当前明确未开放

- [ ] **OCR / 扫描 PDF**：没有本地 OCR，也没有真实外部 OCR/文档分析服务接入；含位图页面仍按 `external_ocr_required` 返回 partial。M3-A/M3-B 的 mock 和 HTTP transport 不构成 OCR 能力。
- [ ] **复杂 PDF 理解**：阅读顺序、表格恢复、标题层级、矢量文字/图形语义和复杂裁切/旋转未验收。
- [ ] **document_understanding 任务目标**：API、CLI、worker、console 的能力清单仍只开放 `native_extract`，不得手工添加目标名。
- [ ] **真实供应商**：Azure Document Intelligence 已作为首个候选并完成离线 REST adapter 基础，但尚未验证项目账户的协议版本、数据区域、隐私边界、SLA、限流、幂等、取消和计费。
- [ ] **真实页图准备**：已完成输入页与 full_page_upright 栅格的摘要、媒体、页集合、旋转和宽高比前置校验；PDF 页面渲染、旋转/裁切效果、像素到 pt 的真实校准仍未完成。当前适配器要求上游提供已验证的 `full_page_upright`。
- [ ] **PDF 渲染器**：已完成显式 Renderer 注入、源字节预检和页图资源预算；尚未选择或安装具体非模型渲染库，也未完成进程级超时、字体、裁切、旋转、质量和许可证验收。
- [ ] **真实效果**：没有去敏中文标注集、文字/区域/表格指标或人工抽查结果，不能报告 OCR 准确率。
- [ ] **异步远端恢复**：Azure adapter 可保留远端 job ID 并在未知/超时错误上停止自动重试；ProviderInvocation、query/cancel、崩溃恢复和重复计费保护尚未接入产品持久化。
- [ ] **调用账目持久化**：已完成 SQLite schema 版本、ProviderInvocation 写入/读取、幂等冲突、状态迁移和并发保护；worker 崩溃恢复、真实幂等/query/cancel、账单证据和长期保留仍未完成。
- [ ] **Provider 生命周期接入**：已完成内部 Coordinator 的计划、提交、终态、显式 retry 和恢复查询；worker 调用顺序、远端 query/cancel、artifact 发布和 API/console 展示仍未完成。
- [ ] **页级 Provider 执行**：已完成未注册的同步执行边界和 unknown 保护；真实 worker 子进程、异步 job、artifact/ParseResult 事务和产品路由仍未完成。
- [ ] **费用闸门**：token/金额预算、账单核对和未知扣费状态策略尚未定义；未知费用不得写 0。
- [ ] **真实音视频工具链**：M4-A 仅完成 ffprobe 进程边界和合成 JSON 契约；实际 FFmpeg/ffprobe 版本、许可证构建、编解码器覆盖、转码/分段和真实 VFR PTS 尚未验收。
- [ ] **外部 ASR 与场景能力**：尚未定义并接入外部 ASR、字幕、PySceneDetect 场景结果的产品契约；不得安装 Whisper、神经 VAD 或本地视觉模型。
- [ ] **ASR 真实联调**：M4-B 已定义独立外部 ASR 契约和离线 HTTP adapter；真实供应商选择、效果/语言、异步恢复、分段去重、计费和 `transcribe`/`video_understanding` 产品路由仍未完成。
- [ ] **场景检测真实接入**：M4-C 已完成不含解码器的 PTS/覆盖/区间关联规则；PySceneDetect 版本与 detector 参数、真实帧抽样、黑帧/淡入淡出和跨轨同步仍未验收。
- [ ] **音频分段与字幕产品接入**：M4-D 已定义受限重叠 chunk 和 SRT/WebVTT 解析；FFmpeg 实际裁剪、容器字幕抽取、编码延迟、ASR 边界去重和成本账目仍未完成。
- [ ] **M4 真实验收**：M4-A～E 完成离线边界，但没有真实 FFmpeg/ffprobe、PySceneDetect、ASR 账户和去敏音视频集；VFR、无音轨、外部缺段、抽样覆盖、效果与费用仍不得宣称完成。

## M1/M2 仍待完成

- [ ] 逐单元进度、执行恢复、数据库迁移、产物保留/回收和孤儿产物治理。
- [ ] 主仓消费 `0.2.0-draft.1` 的显式迁移评审和快照更新。
- [ ] 复杂 Office 特性与真实中文资料的人工验收。
- [ ] 项目许可证确认、发行清单和跨平台干净环境验证。

## 后续开发顺序

1. 先确定真实文档分析服务和数据边界，写 `testing/changes/*-before.md`；Azure 当前只是候选，不等于生产选定。
2. 完成真实服务专用 adapter 的联调；保留通用 transport，不能让厂商响应直接进入公共契约。
3. 完成页图渲染和几何映射，保存原始响应/派生关系，补真实标注集和效果报告。
4. 定义新版本 `document_understanding` 结果与调用账目，再接入 Store、worker、API 和 console。
5. 只有真实效果、成本、失败/取消/恢复和安全边界通过后，才更新 catalog/capabilities 为 enabled。

## 不应提前做的事情

- 不安装或下载 Tesseract、PaddleOCR、Whisper、VLM、ONNX 或任何本地模型/权重。
- 不把人工编写的 mock 文本、供应商 benchmark、单次成功请求或 UI 状态当作效果验收。
- 不在 PDF 含图片时用页眉或原生文字推断整页已读。
- 不在没有新契约和主仓迁移评审时把外部识别块写进现有 ParseResult。
- 不因前端需要展示而伪造 OCR 进度、置信度、费用、心跳或完整状态。

关联记录：[M3-A](m3-document-analysis.md)、[M3-B 开发前](../testing/changes/2026-10-22-m3b-http-provider-before.md)、[M3-B 开发后](../testing/changes/2026-10-22-m3b-http-provider-after.md)。
