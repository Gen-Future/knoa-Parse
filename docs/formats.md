# 资料类型与目录划分

本页保留完整格式规划；当前开放 UTF-8 TXT、JSON 及文档组中的 DOCX/PPTX/XLSX/原生 PDF，其余后缀未启用。P0/P1/P2 是建议实现顺序，不是已支持等级。机器可读清单见 [catalog.json](../src/knoa_parse/parsers/catalog.json)，其中首批候选和后续格式分别列出。

| 家族 / 目录 | 常见资料 | 主要处理方式 | 必须保留的定位与结构 | 建议阶段 |
| --- | --- | --- | --- | --- |
| text | TXT、Markdown、日志、RST、源代码文本 | 解码、段落/标题/代码块；不执行代码 | 原文字符偏移、行号、编码与转换映射 | P0 |
| structured | JSON、JSONL、XML、YAML | 使用成熟解析器读取树或记录 | 记录序号、JSON Pointer/节点路径、原始标量类型 | P0 |
| pdf | 文字型、扫描型、混合 PDF | 原生文字/几何提取；按页选择外部 OCR/文档分析 | 页、区域、阅读顺序、表格、原生/OCR 来源 | P0 起，扫描增强 P1 |
| document | DOCX；后续 DOC、ODT、RTF | 原生段落/表格/图片/批注；必要时 Office 转换 | 段落、表格单元格、关系 ID；渲染页只属于派生产物 | P0 |
| presentation | PPTX；后续 PPT、ODP、Keynote | 幻灯片文本、形状、表格、备注；渲染与外部视觉补充 | 幻灯片序号、形状 ID、区域、备注与正文区分 | P0 |
| spreadsheet | XLSX、CSV、TSV；后续 XLS、XLSB、ODS | 原生读取表格；公式与缓存值分开 | sheet ID/名称、A1 范围、合并单元格、类型、隐藏状态 | P0 |
| image | PNG、JPEG、WebP、TIFF；后续 HEIC、BMP、GIF | 解码、方向/尺寸；外部 OCR 或视觉服务 | 图像/帧、坐标系、旋转映射、文字与描述分别标记 | P1 |
| audio | WAV、MP3、M4A、FLAC、OGG；后续 AAC、OPUS | 探测、转码、分段；外部 ASR | 原音轨、毫秒时间段、分段偏移、语言、可选说话人 | P1 |
| video | MP4、MOV、MKV、WebM；后续 AVI | 音轨/字幕/视觉三支路，抽帧后外部 OCR/视觉 | 原视频时间线、流 ID、帧时间、转录与画面分别归因 | P1 |
| web | HTML、HTM；后续 MHTML | 快照上的 DOM/正文提取；动态页面采集另设接入能力 | URL、快照摘要/时间、DOM 位置、正文与表格 | P1 |
| ebook | EPUB；后续 MOBI、AZW3、PDF 电子书归 pdf | 容器清单、spine 顺序、XHTML 内容读取 | 章节顺序、内部资源路径、元素锚点；不伪造页码 | P2 |
| email | EML、MBOX；后续 MSG | MIME 正文、多语言头部、附件与邮件串 | 消息 ID、MIME part、附件关系；HTML/纯文本去重 | P2 |
| archive | ZIP、TAR、TAR.GZ；后续 7Z、RAR | 受限展开并对子文件重新路由 | 容器路径、条目路径、各子文件摘要与失败状态 | P2 |

## 为什么这样分

- “视频”和“音频”独立：视频同时包含视觉与声音，单独转录不能覆盖画面信息；两者只共享媒体工具和 ASR 接口。
- “PDF”和“Word”独立：PDF 以固定页面为中心，DOCX 以文档结构为中心；转换为 PDF 只是辅助分支。
- “PPT”和“Excel”独立：前者以幻灯片和形状为基本单元，后者以工作表和单元格为基本单元。
- “CSV/TSV”归 spreadsheet；“JSON/XML/YAML”归 structured，避免同一扩展名有多个家族争抢。
- Markdown 和代码默认作为资料读取，不进行业务含义解释或执行；字幕 SRT/VTT 是音视频支路的辅助输入，暂不新增顶层家族。
- 扫描型 PDF 是 pdf 的处理策略，不再建 scan_pdf 家族。图表、表格、公式是内容块/能力，不是输入资料家族。

## 复合资料与未覆盖类型

邮件附件、Office 内嵌对象、EPUB 图片和视频音轨通过子任务分派复用对应家族。加密资料需要调用方提供访问能力，否则明确返回不能读取，不尝试绕过。

OFD、LaTeX、专业 CAD、数据库文件和设计源文件不纳入首批；如新增需求，先确认定位模型与现成工具，再决定新家族还是现有家族扩展。云端 Docs/Sheets/Slides、网页链接和聊天记录导出属于“来源或业务语义”，应先获取具体快照/导出格式，再进入上述家族。
