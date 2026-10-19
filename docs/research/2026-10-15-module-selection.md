# 解析模块横向调查与选型结论

日期：2026-10-15。结论适用于 Knoa Parse：独立解析产品、单机首版、统一 API/CLI、可追溯证据、禁止本地模型与模型下载。不是对各项目总体质量的排名。

本报告替代上一份报告中预设 Docling 与 RAG-Anything 双主线的建议。项目名只是候选线索；采用单位必须是有明确职责、依赖边界和验收标准的模块。

## 1. 调查方法与证据等级

按五个条件依次筛选，不用 Star 数或未经复现的性能分数加权：

1. 任务匹配：是否直接解决格式结构、来源定位或确定性媒体处理，而非同时建设 RAG、应用 UI、索引和推理服务。
2. 模型边界：默认路径和传递依赖是否引入推理、权重下载或基于模型的检测；不仅检查 OCR 开关。
3. 可分离性：有无可使用的公开模块入口；拆除不需要的功能后要维护多少内部类型和调用链。
4. 成熟证据：发布记录、模块级回归、具体缺陷反馈、可读实现；存在测试不等于所有格式都正确。
5. 总成本：安装依赖、系统组件、运行内存、代码改动、升级与定位损失一起考虑；代码行数少不等于接入成本低。

已读依赖声明、关键处理源码、部分模块测试、问题记录和发布元数据。[证据清单](2026-10-15-selection-evidence.json) 保存 34 条文件记录，其中 Docling 的关键文件已按发布提交重读。其他默认分支文件以 blob SHA 标识，尚未作为生产锁定版本。

未执行上游安装、完整依赖解析、真实解析和性能基准。终端访问 PyPI 遇到 DNS 解析失败；GitHub 连接器和浏览器读取正常。因此本报告给出明确的方案选型和拒绝理由，运行准入另设门槛，不编造包体积、内存、速度或准确率。

## 2. 结论矩阵

“采用”表示方案选择，尚不是运行时已启用；“按需”不进入首版默认安装；“参考”不产生包依赖或预设源码搬运任务。

| 候选项目/模块 | 判定 | 核心理由 | 不带入的部分 |
| --- | --- | --- | --- |
| Docling 原生文档 backend + SimplePipeline | 采用，文档主引擎 | 已有结构组织、图表/备注/脚注等处理和回归；按格式 extras 可收敛依赖 | 本地模型、chunking、Serve、UI、音视频、通用信息抽取 |
| Docling NativePdfPipeline | 采用，原生 PDF 证据读取 | 页、文本单元、图片和区域可整体复用；与文档主引擎共用结果体系 | 不把标准 PDF 本地模型管线带入，不宣称具备复杂布局/表格恢复 |
| RAG-Anything | 仅设计参考，不安装、不预设拷贝 | 许多解析能力来自下层项目；上下文窗口逻辑可参考，但顶层依赖和输出语义不适合 Parse | LightRAG、MinerU 默认依赖、本地 Whisper、图谱/向量库、查询、整套模态处理器 |
| PySceneDetect AdaptiveDetector/ContentDetector | 视频阶段采用 | 专门场景检测实现，有相应测试，能够绕过 RAG 包装层 | MoviePy、剪辑导出、报告 UI、额外 OCR/ASR；使用 headless 分发 |
| FFmpeg/ffprobe | 音视频阶段采用 | 媒体流探测、音轨、字幕和帧处理的基础；不复制编解码实现 | 自带媒体编辑产品、模型推理、第二套下载器 |
| Trafilatura 正文提取入口 | 网页阶段按需采用 | 正文去噪是独立问题，有专门实现与评测；不要求再引入综合解析框架 | 抓取、爬虫、全量 extras、语言模型；输出是正文派生视图 |
| Unstructured | 首版不接入 | partition 能力成熟，但当前基础 NLP 与部分格式路径带来模型/额外依赖；与主引擎职责重叠 | 全包、ingest、默认 NLP 和 PDF 推理；只参考元素/策略设计 |
| MarkItDown | 首版不接入 | Markdown 导向不满足完整证据；主入口包含模型式格式识别，重叠能力多 | 全包、Magika、其音频/云端插件；导出设计可参考 |
| MinerU | 不接本地包；未来可评估托管结果接口 | 当前基础依赖含推理/下载/界面组件，难以作为本项目的轻量本地基座 | 本地后端、模型服务、WebUI、资料管理与路由产品 |
| Marker | 首版不接入 | 核心依赖含 Torch、Transformers、Surya；其主要质量路径不符合本地模型限制 | 全包及默认模型流程；处理阶段设计可参考 |
| Kreuzberg LTS / Xberg | 首版不接入现成 Python 包 | Rust 本身不是障碍；当前 Python 绑定启用的功能范围过宽，裁剪需承担自建二进制发布 | OCR、布局模型、embedding、MCP/API 等；保留未来替代引擎资格 |
| DocVortex | 首版不接入现成包 | 原生解析值得关注，但当前包包含 Magika/ONNX，自动模式可下载并运行 OCR；旧介绍已不能代表当前边界 | 全包、自动 OCR 和大量导出链；以后若有可验证精简分发再评估 |
| Apache Tika | 旧格式需求明确后专项评估 | 广格式/遗留资料价值明确；当前引入 JVM 或服务会增加运维，standard package 范围也很广 | 默认全包、OCR/ML、独立服务；不能只为一两个后缀增加 JVM |

方案保留一个通用文档引擎，以及按需的媒体、正文专门模块。底层语法/容器工具仍可使用，不为“必须接一个大项目”引入重复高层系统。

## 3. 决定取舍的源码证据

### Docling：可以采用，但必须限制能力与版本

[PyPI 发布](https://pypi.org/project/docling-slim/2.139.0/) 确认 2.139.0 已发布，发布来源提交为 `6b77e54c8c83ac46c9c0aa126e2761f57c93e44e`。本轮按此提交重读关键 backend、原生 PDF 和包配置，内容与先前主分支记录一致。它是集成实验基线，不意味着最新版本已经通过 Knoa 验收。

其 [精简包配置](https://github.com/docling-project/docling/blob/6b77e54c8c83ac46c9c0aa126e2761f57c93e44e/pyproject.toml) 能分开选择格式与模型能力。但 [docling-core](https://github.com/docling-project/docling-core/blob/main/pyproject.toml) 自身仍依赖 pandas 等组件，convert-core 包含 SciPy/空间索引等；不能把 slim 说成没有成本。当前文档转换入口仍导入多种 backend/pipeline，需要用锁定环境核对导入链。

[Word backend](https://github.com/docling-project/docling/blob/6b77e54c8c83ac46c9c0aa126e2761f57c93e44e/docling/backend/msword_backend.py) 包含嵌套列表、图表、页眉页脚、脚注与批注组织；[对应测试](https://github.com/docling-project/docling/blob/main/tests/test_backend_msword.py) 覆盖多项边界。复用这些高层积累有实际意义，没必要重新基于 python-docx 开发同等遍历器。

[Excel backend](https://github.com/docling-project/docling/blob/6b77e54c8c83ac46c9c0aa126e2761f57c93e44e/docling/backend/msexcel_backend.py) 用 `data_only=True` 读取，其表格单元输出主要是文本、跨度和局部索引；[测试](https://github.com/docling-project/docling/blob/main/tests/test_backend_msexcel.py) 也明确验证缓存计算值。公式、原始类型、数字格式和行列隐藏状态需要额外保留。[公式/格式问题](https://github.com/docling-project/docling/issues/4619) 与 [隐藏行列问题](https://github.com/docling-project/docling/issues/4620) 提供验收线索；这些报告不作为所有版本永远有缺陷的证明。

结论：复用其工作表内容区域组织，另设有限的单元格原始字段读取与关联；不把 Docling 表格文本当完整 Excel 数据。当前表格 provenance 的 bbox 使用行列位置，不能误当 PDF 点数或屏幕像素。

[NativePdfPipeline](https://github.com/docling-project/docling/blob/6b77e54c8c83ac46c9c0aa126e2761f57c93e44e/docling/pipeline/native_pdf_pipeline.py) 明确不做阅读顺序、标题或表格恢复。采用它获取原生证据；复杂 PDF 的版面/表格/OCR 接外部文档分析，由 Knoa 做结果合并，不改造整个标准模型管线。

### RAG-Anything：设计价值高于本期直接接入价值

[包配置](https://github.com/HKUDS/RAG-Anything/blob/main/pyproject.toml) 基础依赖包含 LightRAG、MinerU 和 huggingface_hub；video extra 又含 SceneDetect、MoviePy、faster-whisper、OpenCV。仅因为它支持多模态，就接入其整套处理器，会重复引入本项目不需要的产品层。

[ContextExtractor](https://github.com/HKUDS/RAG-Anything/blob/main/raganything/modalprocessors.py) 实质包含相邻页/块筛选、图注/标题拼接和长度裁剪，返回字符串；无 tokenizer 时用字符长度代替 token 数，异常可返回空字符串。Knoa 要返回上下文 block 引用、实际截断记录和显式错误。直接迁移需要较多语义改造，当前没有证据表明优于按本项目契约实现这段有限胶水逻辑。

因此撤销“必须抽取 ContextExtractor 和视频处理器”的实施任务：借鉴“模态内容附带邻近上下文、音画按时间关联”的设计；场景检测直接采用其底层专门项目。将来若发现有独特复杂算法且测试与依赖闭包可分离，再提出源码迁移，不预留一整个 RAG-Anything 模块目录。

### PySceneDetect：专门模块优于间接包装

[AdaptiveDetector](https://github.com/Breakthrough/PySceneDetect/blob/main/scenedetect/detectors/adaptive_detector.py) 在内容变化评分上使用邻近窗口，属于非神经场景检测；[测试](https://github.com/Breakthrough/PySceneDetect/blob/main/tests/test_detectors.py) 覆盖切镜、渐变和最短场景等行为。[headless 分发配置](https://github.com/Breakthrough/PySceneDetect/blob/main/packaging/variants/pyproject-scenedetect-headless.toml) 只需相应非模型依赖，不选 MoviePy/PyAV extras；官方 [0.7.2 分发](https://pypi.org/project/scenedetect-headless/0.7.2/) 可作为视频实验基线。

它仍引入 OpenCV，不能称零成本。[VFR 帧号问题](https://github.com/Breakthrough/PySceneDetect/issues/569) 和 [场景终点问题](https://github.com/Breakthrough/PySceneDetect/issues/561) 提醒我们：场景检测结果只是候选分段，定位以解码得到的时间戳为准，不能默认 frame/FPS 正确。冻结版本后用合成 VFR 样例验收，无法映射则明确拒绝该模式或改用带真实时间戳的定时采样。

### 其他候选的具体拒绝或延后依据

- **Unstructured**：[基础依赖](https://github.com/Unstructured-IO/unstructured/blob/main/pyproject.toml) 包含 spaCy、Numba 等；[tokenize.py](https://github.com/Unstructured-IO/unstructured/blob/main/unstructured/nlp/tokenize.py) 具有缺少 spaCy 模型时下载安装的路径。它不符合“装一个无模型 partition 包就够”的假设；其 [XLSX](https://github.com/Unstructured-IO/unstructured/blob/main/unstructured/partition/xlsx.py) 也不是完整电子表格语义替代品。排除整包，不否定单个算法未来价值。
- **MarkItDown**：[入口](https://github.com/microsoft/markitdown/blob/main/packages/markitdown/src/markitdown/_markitdown.py) 构造 Magika 并调用内容识别；[Magika 官方配置](https://github.com/google/magika/blob/main/python/pyproject.toml) 明确其深度学习用途。去掉识别仍需解决 Markdown 丢失结构的问题，与已有引擎相比缺少本期独特收益。
- **MinerU**：[当前依赖](https://github.com/opendatalab/MinerU/blob/master/pyproject.toml) 包含 ONNX Runtime、模型下载组件、Gradio、服务与本地推理相关组件。使用它自己的远端服务可以另作 Provider 决策，但不应为发送 HTTP 请求先安装整个本地产品。
- **Marker**：[依赖](https://github.com/datalab-to/marker/blob/master/pyproject.toml) 包含 Torch、Transformers、Surya。接一个外部 LLM 并不能移除其其他本地模型阶段。当前不为复用少量后处理代码承担整套模型类型依赖。
- **Kreuzberg / Xberg**：检查了 [Kreuzberg Python 绑定](https://github.com/kreuzberg-dev/kreuzberg-lts/blob/main/crates/kreuzberg-py/Cargo.toml) 与 [Xberg Python 绑定](https://github.com/xberg-io/xberg/blob/main/crates/xberg-py/Cargo.toml)，对应构建开启 full 或广泛模型功能。运行时关闭 OCR 不会消除分发包里的依赖。自建精简 Rust wheel 有可能，但首版不承担另一套跨平台构建/修补链；若未来有官方可用的精简 wheel，重新比较。
- **DocVortex**：旧搜索摘要与当前文档不一致。当前 [依赖](https://github.com/myhloli/DocVortex/blob/main/pyproject.toml) 包含 Magika/ONNX Runtime，[使用文档](https://github.com/myhloli/DocVortex/blob/main/docs/USAGE.md) 描述 auto/ocr 路径及首次权重下载。强制 txt 能避开部分路径，但不满足当前依赖最小化目标；不复制其整个转换/渲染树。
- **Tika**：[standard package](https://github.com/apache/tika/blob/main/tika-parsers/tika-parsers-standard/tika-parsers-standard-package/pom.xml) 聚合许多模块，包括 OCR/ML 相关项。按需拆模块可研究，但只有明确的遗留格式收益足以支付 JVM 与部署成本时才考虑。
- **Trafilatura**：[core](https://github.com/adbar/trafilatura/blob/master/trafilatura/core.py) 提供独立正文提取入口，[配置](https://github.com/adbar/trafilatura/blob/master/pyproject.toml) 可不装 all extras。[评测说明](https://github.com/adbar/trafilatura/blob/master/tests/README.rst) 明确主要检查文本片段，不评估全部顺序，因此不能把它当无损 DOM 解析器或引用定位器；只在网页正文视图阶段采用。

## 4. 接入与冗余边界

| 接入单位 | 允许进入 Knoa 的内容 | 明确不进入 |
| --- | --- | --- |
| Docling 适配 | 选定格式配置、转换调用、完整上游产物、结构/定位映射 | Docling Serve、示例应用、默认模型管线、通用 chunker、第二套任务系统 |
| Excel 原始字段补充 | 工作表/A1、原始值/类型、公式、缓存、格式、合并/隐藏；与上游区域关联 | 公式计算引擎、Excel 渲染器、重新实现文档分区算法 |
| 媒体适配 | FFmpeg/ffprobe 受控操作，选定场景检测器与时间映射 | MoviePy 编辑层、完整视频理解框架、本地 ASR/VAD/说话人模型 |
| 外部能力 | 统一能力接口，所选供应商的最薄 HTTP/SDK 适配 | 供应商 UI、训练/推理服务、上游业务存储、无关云 SDK 集合 |
| 内容增强 | 结构邻近上下文、预算、外部调用、推断与来源关联 | 实体知识图谱、向量索引、检索、Agent 框架、长期记忆 |
| 网页正文 | 已保存 HTML 的正文派生结果 | 爬虫、浏览器集群、联网重抓和自动插件发现 |

第三方 wheel 中未使用的普通源码文件并不自动值得删除。我们控制安装依赖、执行路径、部署组件和本地维护范围；为删除少量惰性源码长期维护 fork，通常会增加总成本。禁止把整个仓库复制进 vendor，禁止通过 `--no-deps` 制造表面精简但不受支持的环境。

## 5. 最终建议与未验证项

采用“一套通用文档转换 + 少量专门模块 + 自有证据/服务边界”。首版不复制任何大型项目的完整处理器，RAG-Anything 不作为必选源码来源。保留按证据提出小范围源码迁移的通道。

仍需实际验证：固定环境的全部传递依赖、无模型冷启动、中文复杂样例、结构/来源映射、外部模型替换质量、安装/内存/时间成本。相关验收必须先于生产启用；无需等这些实验完成才明确本轮排除哪些包。完整实现、资源约束和失败分支见 [实现方案](../implementation-plan.md)。
