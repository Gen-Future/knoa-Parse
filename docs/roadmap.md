# 解析层实施路线

当前路线依据 [横向选型](research/2026-10-15-module-selection.md) 和 [完整实现方案](implementation-plan.md)，替代此前预设迁移 RAG-Anything 的任务。

## 已落实

- [x] 13 个资料家族、规划 catalog、外部模型与证据边界。
- [x] 对通用解析、RAG、多模态、网页与视频项目做横向源码/依赖调查。
- [x] 明确采用一个 Docling 文档引擎，媒体与正文模块按阶段加入。
- [x] RAG-Anything 改为设计参考，不安装、不预设代码搬运；明确其他整包拒绝理由。
- [x] 补充 Excel 原始语义、定位精度、依赖分组、成本记录、失败退出与升级规则。

## M0：先验证选型成立

- [x] 冻结发布版本与全部依赖，验证 Python 3.12 环境。
- [ ] 确认项目许可证后完成发行准备。
- [x] 原生格式导入/执行无本地模型；依赖锁和安装闭包审计通过。
- [x] 验证上游结构映射和 Excel 原始字段关联；记录分组环境及进程观察。
- [ ] 未通过的格式限制范围或重选，不扩大默认依赖作为补救。

## M1：契约与产品闭环

- [x] 落地初始新版本 Schema、示例、版本索引及旧版回归。
- [x] 实现初始统一 API/CLI、任务/产物存储、租约、子进程、取消和资源限制。
- [ ] 实现逐单元执行恢复、进度、迁移及产物保留/回收。
- [ ] 明确主仓消费影响，经评审后显式同步快照。

## M2：文档格式

- [x] Docling 适配、Office/原生 PDF 映射、Excel 原始字段补充。
- [x] 验证初始合成样例、定位精度、缺口与资源上限，开放六种后缀的原生目标。
- [x] 增加 15 个独立语义预期样例，覆盖脚注/修订、分组/图表、纯公式/隐藏、中文/旋转/混合 PDF；依据见 [覆盖记录](../evals/m2-coverage.md)。
- [ ] 扩充复杂 Office 特性与真实中文样例，逐项记录覆盖。

## M3：外部文档能力

在进入 M3 前，按用户要求插入了可选观测工作台：独立 apps/console、通用只读最近任务/来源接口、任务提交与证据检查。前端不成为解析运行依赖，不改变 M2 完整性标准或后续模型接入边界；见 [ADR 0005](adr/0005-optional-observation-console.md)。

- [x] M3-A：同步单页内部 Provider 协议、显式 dry-run mock、独立页级合并、上下文引用与调用/输入/输出预算；见 [说明](m3-document-analysis.md)。不属于已开放产品能力。
- [x] M3-B-基础：通用 HTTPS/JSON 文档服务 transport、响应边界和错误归一化；见 [开发后记录](../testing/records/2026-10-22-m3b-http-provider.md)。未绑定厂商且未开放产品能力。
- [x] M3-C：PDF 原生页与已准备 full_page_upright 栅格的来源、SHA、媒体、页集合、旋转和宽高比前置校验；见 [开发后记录](../testing/records/2026-11-02-m3c-page-input.md)。不包含渲染或 OCR。
- [x] M3-D：Renderer 注入边界、Source 完整性预检、页数/像素/单页/总输出预算和 M3-C 原子接入；见 [开发后记录](../testing/records/2026-11-02-m3d-renderer-boundary.md)。不包含具体渲染库。
- [x] M3-E-基础：Provider 调用账目模型、状态不变量、unknown/query/manual 恢复决策和重试闸门；见 [开发后记录](../testing/records/2026-11-03-m3e-invocation-recovery.md)。未持久化、未接入真实服务。
- [x] M3-F-基础：SQLite schema 迁移、账目幂等写入、状态迁移、并发冲突和 read-only 查询；见 [开发后记录](../testing/records/2026-11-03-m3f-ledger-store.md)。未接入 worker/真实服务。
- [x] M3-G-基础：Provider 调用生命周期协调器，统一计划、提交、成功/失败/unknown/取消、显式 retry 和恢复查询；见 [开发后记录](../testing/records/2026-11-03-m3g-invocation-coordinator.md)。未接入 worker/真实服务。
- [x] M3-H-基础：页级 Provider 执行边界、artifact 发布顺序、取消/unknown 保护和多页 outcome；见 [开发后记录](../testing/records/2026-11-04-m3h-provider-execution.md)。未接入真实服务/产品 worker。
- [x] M3-I-基础：Azure Document Intelligence REST adapter 的单页提交、异步轮询、远端 job 保留、稳定错误和保守文本/几何映射；见 [开发后记录](../testing/records/2026-11-04-m3i-azure-adapter.md)。未注册产品路由，不代表 OCR 已开放。
- [ ] M3-B-产品：真实服务选型与适配、页图准备/映射、原始响应持久化、新目标契约、页级恢复和产品路由；同步时限与费用预算需按服务能力进一步落实。
- [ ] 选服务后真实联调；扫描/复杂 PDF 通过效果验收才启用。

## M4：音频与视频

- [x] M4-A-基础：引擎无关媒体流/时间基/PTS 契约与受控 ffprobe 边界；见 [开发后记录](../testing/records/2026-11-04-m4a-media-probe.md)。未安装或锁定实际二进制，未开放音视频产品能力。
- [x] M4-B-基础：供应商无关的外部 ASR 单片段契约、时间偏移、词级结果和 HTTPS/JSON transport；见 [开发后记录](../testing/records/2026-11-04-m4b-asr.md)。未接真实服务、未开放转录目标。
- [x] M4-C-基础：基于实际帧 PTS 的场景候选、抽样覆盖与音频/字幕/转录区间关联；见 [开发后记录](../testing/records/2026-11-04-m4c-scene-timeline.md)。未安装 PySceneDetect，未开放视频理解。
- [x] M4-D-基础：受服务上限约束的音频重叠分段、core 去重区间和 SRT/WebVTT 时间映射；见 [开发后记录](../testing/records/2026-11-04-m4d-timeline.md)。未执行真实裁剪/字幕容器抽取。
- [x] M4-E-基础：无音轨前置、chunk 覆盖/缺段和费用 unknown 闸门；见 [开发后记录](../testing/records/2026-11-04-m4e-media-gates.md)。真实工具/服务效果仍未验收。
- [ ] M4-真实验收：FFmpeg/ffprobe 与 PySceneDetect 版本、外部 ASR、字幕/场景/转录关联、VFR/无音轨/覆盖和费用通过真实资料验收后才开放目标。
- [ ] 验证 VFR 与实际 PTS、抽样覆盖、无音轨、外部缺段与费用边界。
- [ ] 仅转录与完整音画目标分开声明，mock 不构成真实能力证明。

## M5：按需长尾

网页正文明确需要时加入 Trafilatura；电子书、邮件、归档和旧 Office 按真实需求选择模块，每次记录依赖增量、定位和错误样例。

当前已完成六种后缀的初始原生闭环、依赖锁、Windows 迁移验证及扩展合成验收；真实中文资料与复杂特性尚未全面验收。Docling 技术验证已完成，完整发布和后续模型/媒体阶段继续按上表推进。详见 [实施记录](implementation-status.md)。
