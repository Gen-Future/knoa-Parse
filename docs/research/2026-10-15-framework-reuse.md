# 成熟解析项目的模块复用调研

> 前次候选调查，保留源码观察。以下预设迁移 RAG-Anything 的建议已被更全面的 [横向选型](2026-10-15-module-selection.md) 替代；它当前仅作设计参考，不进入默认依赖或源码迁移计划。

调研日期：2026-10-15。通过官方 GitHub 源码及 Docling、RAG-Anything 官方文档核对模块。本轮没有安装或运行这些项目，没有复制上游代码，也没有验证真实服务效果。以下是有源码依据的集成候选，不是已交付能力。

本报告修正 [上一轮调研](2026-10-14-parser-landscape.md) 的采用方向：首先寻找成熟项目已经完成的高层能力，然后判断直接调用、源码抽取或设计借鉴；底层库是实现基础和缺口补充。Docling 自身也使用 python-docx、python-pptx、openpyxl，价值在于这些依赖之上的转换和文档组织逻辑。

## 1. 总体分工

| 能力 | 优先研究对象 | 拟采用方式 | 必须保留的边界 |
| --- | --- | --- | --- |
| Office、HTML/Markdown 等结构化文档转换 | Docling 的格式 backend + SimplePipeline + DoclingDocument | 通过内部 engine 直接调用完整转换能力，必要时补充定位适配 | 逐格式验证覆盖；不可假设所有原始对象 ID 和单元格信息都完整保留 |
| PDF 原生内容与几何提取 | Docling NativePdfPipeline | 依赖调用，保留页面、图片、区域和过程状态 | 不承担复杂阅读顺序、标题及表格恢复；需要外部文档分析增强 |
| 图像、表格、公式的上下文组织 | RAG-Anything ContextExtractor 及模态描述流程 | 抽取并改造模块，移除 LightRAG 依赖，模型回调接 Provider | 增强描述与原文分开；图谱、向量索引和检索不进入 Parse |
| 视频分镜、场景上下文和音画对齐 | RAG-Anything VideoModalProcessor 的非模型方法 | 选择性迁移流程及测试，音轨转录接 AsrProvider | 排除本地 Whisper；保留实际时间戳、缺段及采样覆盖，不只输出拼接文本 |
| 上游结果兼容 | RAG-Anything 的 Docling/MinerU 内容转换模块 | 借鉴遍历和版本兼容；需要特定输入时再抽取转换器 | canonical 结果不能经由有损 content_list 中转 |
| 尚未覆盖的复杂文档/长尾格式 | MinerU、Unstructured、Marker 等 | 有具体缺口后进行同等深度的模块评估或服务适配 | 不同时整包引入全部框架；不采用本地模型默认路径 |

## 2. Docling：优先复用转换实现

### 原生格式转换

[document_converter.py](https://github.com/docling-project/docling/blob/main/docling/document_converter.py) 为 Word、PowerPoint、Excel 等配置格式 backend 和 SimplePipeline。[SimplePipeline](https://github.com/docling-project/docling/blob/main/docling/pipeline/simple_pipeline.py) 调用 declarative backend 的 convert，产出统一文档。

这是一条值得整体接入的转换路径。Knoa 不再默认分别用 python-docx、python-pptx、openpyxl 重写一遍上层遍历、内容组织和统一输出。由 DoclingEngine 选择格式配置，保存完整上游输出，再映射为 Knoa 证据。

来源定位是独立验收项：如果上游遗漏 XLSX 单元格地址、公式语义或 PPT 形状标识，先检查 backend 是否已有可用数据或扩展点，再考虑最小补丁或补充读取。不能为“统一接入”接受不可追溯的内容，也不能因此未经验证就重写整个格式解析器。

### 无模型 PDF 管线的实际能力

[NativePdfPipeline](https://github.com/docling-project/docling/blob/main/docling/pipeline/native_pdf_pipeline.py) 明确采用原生 PDF 文本单元、图片和可选页面渲染，构建带区域来源的文档项；还包含页处理、进度、超时和部分完成状态。

它明确不做模型版面分析、OCR 或表格识别，也不恢复标题和阅读顺序；内容顺序来自 backend。可以复用它作为原生证据层，不能称为继承了 Docling 默认 PDF 管线的全部解析质量。

复杂 PDF 的计划路径是：原生页级证据 → 判断需要增强的页 → 外部文档分析/OCR → 映射与合并。标准 PDF 管线有其他本地模型阶段，仅关闭 OCR 不足够。能否利用 Docling 现有扩展点替换各阶段，要在冻结版本后验证；不能承诺只换一个 endpoint 即完成。

### 按需依赖提供了更好的集成机会

当前主分支 [pyproject.toml](https://github.com/docling-project/docling/blob/main/pyproject.toml) 和 [docling-slim 说明](https://github.com/docling-project/docling/blob/main/packages/docling-slim/README.md) 提供按格式与模型能力划分的 extras。可以研究只包含 Office、非模型 PDF 及必要转换依赖的构建。

主分支存在配置不等于相应稳定发行包已可用。采用前核对发布版本、依赖锁与实际 import 链；converter 会导入多类 pipeline，不能只看依赖声明就宣布精简环境能够启动。音频、视频和 local models 等 extras 不在默认采用范围。名为 remote 的能力也不自动等于无需自建推理的托管服务。

## 3. RAG-Anything：复用组织与增强逻辑，解除项目耦合

### ContextExtractor 是比整包接入更合适的起点

[modalprocessors.py](https://github.com/HKUDS/RAG-Anything/blob/main/raganything/modalprocessors.py) 中 ContextConfig、ContextExtractor 提供按页或内容块选取上下文、标题/图注筛选与长度控制的逻辑。优先研究把这段完整能力与相关测试迁入 enrichment，替换其数据类型和依赖入口。

同文件的 BaseModalProcessor 持有 LightRAG、存储、embedding 与实体处理依赖；图像、表格、公式处理器继承它。即便方法名是 generate_description_only，也不能据此认定处理器脱离 LightRAG 可直接使用。

因此拟保留上下文选择、模态分派、描述请求构造和关联方式，通过 VisionProvider/TextModelProvider 请求外部服务；删除图谱和索引相关职责。原文、上下文引用和模型推断分开保存，不能把生成说明写回原始表格或正文。

### 音视频可以借鉴，但不能复制默认转录链

[modalprocessors_video.py](https://github.com/HKUDS/RAG-Anything/blob/main/raganything/modalprocessors_video.py) 包含场景检测、抽帧、音轨提取、场景描述、时间范围内转录选择与音画合并。它提供可复用的流程积累；其非神经的内容变化检测思路不违反本地模型边界。

但它调用的 [AudioModalProcessor](https://github.com/HKUDS/RAG-Anything/blob/main/raganything/modalprocessors_audio.py) 会构造 faster-whisper 的本地 WhisperModel，转录可启用 VAD。本项目不采用这条实现，音频识别统一替换为 AsrProvider。

适配还需纠正输出语义：失败被转为空转录时不能记完整；用帧数/FPS 推算的时间不能替代可变帧率视频的实际 PTS；上游拼接的场景文字要拆为可追溯的场景、帧和转录关联。这些是迁移后的行为差异，需专门回归。

### 内容转换代码值得参考，但不能成为有损中间层

[parser.py](https://github.com/HKUDS/RAG-Anything/blob/main/raganything/parser.py) 的 DoclingParser 包含 converter 缓存、文档树遍历和 content_list 映射。默认 converter 使用 PDF OCR/表格配置，不能照搬；部分映射只采用第一个来源页，无法完整承载多来源定位。失败说明也不应伪装为正常提取的正文。

Knoa 从 Docling 的完整结果直接映射契约，保留原输出 artifact。RAG-Anything 的 [mineru_content.py](https://github.com/HKUDS/RAG-Anything/blob/main/raganything/mineru_content.py) 可作为未来接入 MinerU 结果时的版本转换候选，当前不因有转换代码就引入整个 MinerU。

此外，包的 [__init__.py](https://github.com/HKUDS/RAG-Anything/blob/main/raganything/__init__.py) 导入上层 RAG 类。不能仅凭 parser.py 未直接导入 LightRAG 就认为从子模块 import 能避开顶层依赖。优先对可分离模块做源码抽取实验，验证真正的依赖闭包。

## 4. 版本证据与许可记录

下列为本轮读取到的文件 blob SHA，用于标识所读内容；链接指向可变化的 main。它们不是项目 commit SHA，也不证明属于某个已发布版本。正式采用时补充不可变提交、依赖锁和完整许可证副本。

| 仓库 | 文件 | blob SHA |
| --- | --- | --- |
| docling-project/docling | docling/document_converter.py | 35bc9663200c56095be4754ad8de53133acc1f50 |
| docling-project/docling | docling/pipeline/simple_pipeline.py | 0e0c8f7a0702dbc2a9675409b77f48b467ec3bfe |
| docling-project/docling | docling/pipeline/native_pdf_pipeline.py | cb744c355f0d2f747579a2d2bb5dcc417a087e48 |
| docling-project/docling | pyproject.toml | f1094732fe7d99d0c099952dda8274c3786d2228 |
| HKUDS/RAG-Anything | raganything/modalprocessors.py | 1a00e588428106a32e9525814773b20d7cf3d833 |
| HKUDS/RAG-Anything | raganything/modalprocessors_audio.py | 90ee3e1a3fee07634e613564b123c6c9b051cc65 |
| HKUDS/RAG-Anything | raganything/modalprocessors_video.py | 98b36f8daaffb32aa2ade27809ca3ac44541bc8c |
| HKUDS/RAG-Anything | raganything/parser.py | 0459fc04e6a38fc884f9d27de1065ed550ac24e8 |
| HKUDS/RAG-Anything | raganything/mineru_content.py | 78add8958cb13cd28cf404242f71d12aa7a4decd |

Docling 仓库标注 MIT；RAG-Anything 的 [LICENSE](https://github.com/HKUDS/RAG-Anything/blob/main/LICENSE) 为 MIT。采用时仍须核对所用版本及传递依赖，保留所要求的许可和版权信息。模型权重、第三方数据集和二进制组件单独核对；本轮未复制代码，无新增第三方代码许可声明。

## 5. 下一步实验而非质量承诺

1. 冻结 Docling 可用版本，尝试无模型依赖组合，验证导入、Office 转换和原生 PDF；保存安装清单与运行记录。
2. 对同一批合成文件记录上游完整结果及 Knoa 映射，测量结构/定位损失，判断可直接复用范围和必须补充的字段。
3. 抽取 ContextExtractor 的最小完整依赖闭包并迁移行为测试，以 mock Provider 验证上下文与增强关联。
4. 评估视频非模型逻辑的抽取量，用 mock ASR/Vision 验证时间对齐与失败语义；真实效果留待外部服务接入后评测。
5. 若抽取需要携带大量 RAG 基础设施，比较局部改造与独立实现的维护成本，记录取舍。没有明确收益就不扩大源码复制范围。

对应决策见 [ADR 0003](../adr/0003-framework-first-reuse.md)，具体交付与验收见 [实现方案](../implementation-plan.md)。
