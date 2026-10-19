# 解析方案调研与取舍

调研日期：2026-10-14。范围为项目官方仓库、文档和部分处理路径源码；Docling 的远端能力另通过 Context7 核对官方资料。此轮未安装这些工具、未运行统一质量基准、未调用付费服务，不依据 Star 数或项目自报分数给出质量排名。

**方向更新（2026-10-15）：本报告的底层库清单保留为基础依赖与对照资料，不再作为默认实现路线。** 当前优先复用成熟项目的完整能力，允许依赖调用、源码抽取改造与设计借鉴。Docling、RAG-Anything 的模块依据见 [后续源码调研](2026-10-15-framework-reuse.md)，最终候选取舍见 [横向选型](2026-10-15-module-selection.md)，采用顺序以 [实现方案](../implementation-plan.md) 为准。以下候选均不是已完成选型。

## 1. 综合框架：借鉴哪些，排除哪些

| 项目 | 官方能力与值得借鉴的部分 | 对 Knoa Parse 的取舍 |
| --- | --- | --- |
| [MarkItDown](https://github.com/microsoft/markitdown/blob/main/README.md) | 多格式转 Markdown、按格式可选依赖、converter/plugin 组织；内置转换器没有通用视频解析，音频转录较基础 | 借鉴轻量转换器注册与可选依赖；可作为导出/对照候选。不把 Markdown 当完整证据契约；不启用未经检查的音频/OCR 插件。代码 [MIT](https://github.com/microsoft/markitdown/blob/main/LICENSE) |
| [Docling](https://github.com/docling-project/docling) | 多格式、统一文档模型、结构与来源关系；[DoclingDocument](https://github.com/docling-project/docling/blob/main/docs/concepts/docling_document.md) 可供内部模型参考 | 更新：优先验证原生 backend、SimplePipeline 和 NativePdfPipeline 的直接复用，保留完整文档与来源；默认本地推理路径仍排除。代码 MIT，模型另有许可 |
| [Unstructured](https://github.com/Unstructured-IO/unstructured) | 按格式 partition、统一元素、不同处理策略 | 借鉴元素类型与按格式分派。库代码 Apache-2.0；选择性复用需审计策略，托管服务可作为外部适配候选 |
| [Apache Tika](https://tika.apache.org/docs/4.1.x/formats.html) | 格式识别、文本/元数据抽取、Office/邮件/复合格式覆盖；能识别的格式比能解析的多 | 广格式与遗留格式候选，尤其选择 Java 技术栈时；不把“识别成功”当“正文提取成功”。OCR/ML 扩展需显式排除；不是统一精细布局的替代品 |
| [MinerU](https://github.com/opendatalab/MinerU) | 当前官方资料包括原生文档与模型处理路径、分层解析、稳定定位及服务能力 | 观察输出、定位和分层思路；不采用其本地模型实现。不能简单称整个项目都依赖本地模型，也不整包引入。当前 [LICENSE](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md) 为基于 Apache 2.0 的附加条件许可，不沿用旧版本印象 |
| [Marker](https://github.com/datalab-to/marker) | 多格式转 Markdown/JSON、处理与渲染阶段、可选 LLM 增强；支持本地模型执行 | 借鉴阶段边界及输出组织，不引入本地模型。当前代码 Apache-2.0、模型权重单列许可，不把代码许可等同权重许可；托管服务是另一个适配决策 |

### 必须防止隐式模型依赖

Docling 的 [standard PDF pipeline 源码](https://github.com/docling-project/docling/blob/main/docling/pipeline/standard_pdf_pipeline.py) 分别创建 OCR、layout 和 table 组件。因此“关闭 OCR”不能证明没有本地模型。其 [高级配置](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md) 已提供远端 OCR、layout、VLM 等接入能力，但开启 `enable_remote_services` 也不等于所有阶段自动变为远端。需要逐阶段确认实现、依赖、首次运行行为与模型下载行为，才可能成为本项目的候选路径。

Unstructured 的 [策略选择源码](https://github.com/Unstructured-IO/unstructured/blob/main/unstructured/partition/strategies.py) 有 fast/hi_res/ocr_only 等分支和依赖触发的回退。不能只设一次 fast 或 auto 就宣布满足边界；应避免隐式进入本地 OCR/推理路径。应对可用的非模型路径做模块级验证；不能因此跳过成熟项目研究，默认重建整套上层流程。

## 2. 按资料类型选择工具

以下作为底层依赖、补充与比较清单保留，不代表要逐个接入。当前先验证 Python 生态成熟项目的完整模块，避免维护多语言业务项目。正式采用时锁定版本、检查传递依赖和该版本许可证。

| 资料/环节 | 优先验证候选与官方来源 | 复用范围 | 限制与验证点 |
| --- | --- | --- | --- |
| PDF 原生文本 | [pypdf](https://pypdf.readthedocs.io/en/latest/user/extract-text.html) | 文本层、文档对象、页处理 | 不是 OCR；扫描 PDF 需外部服务，复杂阅读顺序要实测 |
| PDF 几何/表格 | [pdfplumber](https://github.com/jsvine/pdfplumber) | 字符、线条、矩形、基于布局的表格提取 | 官方明确更适合机器生成的 PDF；不承诺扫描件或任意复杂表格。MIT |
| PDF 渲染 | [pypdfium2 / PDFium](https://github.com/pypdfium2-team/pypdfium2) | 页面渲染和坐标相关基础处理 | 非模型能力；封装与底层/二进制依赖许可分别核对，官方列出 Apache/BSD 等条款 |
| PDF 高性能备选 | [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/about.html) | 文本、几何、图像与渲染 | 只评估非 OCR 路径；官方为 AGPL/商业双许可，许可证决策前不作为默认依赖 |
| PDF JS 备选 | [PDF.js](https://github.com/mozilla/pdf.js) | JavaScript PDF 解析/渲染 | 可供 JS 栈评估；阅读顺序和表格结构仍需验证，不能等同完整文档理解 |
| DOCX | [python-docx](https://python-docx.readthedocs.io/en/latest/) | 原生段落、表格、形状/关系等 | 不负责 Word 分页渲染；复杂文本框、修订、脚注和嵌入对象逐项验证，不假定全部支持 |
| PPTX | [python-pptx](https://python-pptx.readthedocs.io/en/latest/) | 幻灯片、形状、文本和表格；可读取的备注信息 | 不是 PowerPoint 渲染引擎；SmartArt、图表、动画、阅读顺序需额外策略 |
| XLSX | [openpyxl 读取说明](https://openpyxl.readthedocs.io/en/stable/tutorial.html) | 工作表、单元格、合并信息、公式和已有缓存值 | [不计算公式](https://openpyxl.readthedocs.io/en/stable/simple_formulae.html)。不得把缺失缓存值记为 0，不把旧缓存当新计算结果 |
| Office Java 备选 | [Apache POI](https://poi.apache.org/) | Microsoft 文档格式读取；适合 Java 工程 | 按子格式验证 HSSF/XSSF/HWPF/XWPF/HSLF/XSLF 覆盖，不引入第二套自研 Office 解析器 |
| 表格 JS 备选 | [SheetJS](https://github.com/SheetJS/sheetjs) | 电子表格读取，适合 JS 工程 | 官方仓库指向新的主站；选型时核对当前分发源、社区/商业功能边界与版本，不照搬旧 npm 版本 |
| 旧 Office/渲染 | [LibreOffice 转换过滤器](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html) | 用现成转换器处理旧格式或生成视觉派生产物 | 独立进程隔离；字体、布局和转换丢失需要比对。不是所有文件先转 PDF；禁宏与外链，保留原文映射 |
| 音视频 | [FFmpeg](https://ffmpeg.org/ffmpeg.html)、[ffprobe](https://ffmpeg.org/ffprobe.html) | 流探测、解封装、转码、音轨提取、按时间抽帧与字幕处理 | 不做 ASR、语义理解或神经 VAD；原始 PTS/时间偏移需映射。许可证取决于[实际构建选项](https://ffmpeg.org/legal.html)，不能统一标为 MIT 或纯 LGPL |
| HTML 正文 | [Trafilatura](https://github.com/adbar/trafilatura) | 从 HTML 提取正文与元数据；作为正文视图候选 | 仍保存原始 DOM 和来源关系；正文清洗可能丢表格/导航相关信息。当前 Apache-2.0，旧版本许可不同 |
| EPUB | [EbookLib](https://github.com/aerkalov/ebooklib) | EPUB2/3 内容与资源结构读取 | 候选为 AGPL-3.0；许可证未定前不直接引入。优先复用成熟容器/XML工具，EPUB 语义按标准库能力评估，不自研通用转换引擎 |
| 多种电子书转换 | [Calibre](https://github.com/kovidgoyal/calibre) | 广格式电子书转换备选 | 体量和部署成本较高；后续存在 MOBI 等明确需求再评估，不作为起步依赖 |
| 邮件 | [标准库 email](https://docs.python.org/3/library/email.html) | MIME 头部、正文和附件结构；其他语言用同类成熟库 | MSG 不是普通 MIME 文件，需单独适配；不能通过换扩展名复用 EML 路径 |
| TXT/JSON/CSV/ZIP | 所选语言的成熟编码、JSON、CSV、XML、ZIP/TAR 库 | 标准格式读取、容器展开 | 不自研语法解析器；保留类型、顺序和原文关系，XML 实体/压缩膨胀/路径穿越必须限制 |

本轮还未选择图片解码库、Markdown AST 库或 EPUB 最终实现；这些由语言选型后按相同规则补齐，不因此引入本地视觉模型。

## 3. 外部服务：先固定能力，后选择供应商

| 能力 | 已核对的官方实例 | 接口必须预留的差异 |
| --- | --- | --- |
| OCR / 文档版面与表格 | [Azure Document Intelligence Layout](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0) | 页、文本、表格和区域；单位、页编号、异步任务、原文跨度映射 |
| OCR / 文档处理器 | [Google Document AI processor list](https://docs.cloud.google.com/document-ai/docs/processors-list) | 处理器/版本/区域与格式能力不同，不能只存统一 endpoint |
| 语音识别 | [阿里云百炼 ASR 模型](https://help.aliyun.com/en/model-studio/asr-model) | 文件/实时模式、语言、时间戳与分段；模型间能力不同，按能力查询而非假定统一 |
| 图片/视频理解 | [百炼视觉理解](https://help.aliyun.com/zh/model-studio/vision) | 支持图像/视频输入不等于输出精确定位；描述、OCR、时间戳与结构化输出能力要分开声明 |

上述只是接口设计的参照，不代表供应商已经选定，也没有测量中文效果、价格、延迟、区域可用性或数据保留条件。TextModelProvider 保留供应商无关接口，本阶段没有默认模型。

远端 HTTP 地址不必然是托管服务；把本地模型搬到自建 GPU 服务器仍需要自行维护推理，不属于本轮采用方案。优先外部受管服务，具体访问环境与数据发送政策在接入前确认。

## 4. 建议落实顺序

本节原先从小型库起步、最后考虑综合框架的顺序已被替代。当前先验证选定的 Docling 非模型路径和必要原始字段映射；RAG-Anything 仅作设计参考，不设源码搬运任务。之后建设统一契约、文档流程、外部能力与音视频；完整顺序见 [路线](../roadmap.md)。

验收数据应包括混合 PDF、多列、合并单元格/缓存公式、PPT 备注、扫描图像、无音轨视频和长音频分段。具体实验计划见 [evals](../../evals/README.md)。

## 5. 正式采用一个依赖的门槛

每个候选留下一份版本、许可证/二进制构建、支持格式、样例结果、已知缺口及传递依赖记录。执行无凭据/无网络/空模型缓存启动检查，确认不会下载权重或拉起本地推理。完整性、定位、模型调用次数与成本可观察后，再纳入生产依赖。未做这些实验之前，调研结论不能写成质量保证。
