# 多格式结果模型：下一版设计

状态：完整多格式目标设计。初始运行时子集已落地 [0.2.0-draft.1](../contracts/v0.2.0-draft.1/README.md)，已用于文本/JSON 和初始文档路径；更丰富的派生和服务对象继续按阶段实现。现有 [0.1.0-draft.1](../contracts/v0.1.0-draft.1/README.md) 和 Knoa 消费快照保留不变；本页不向它追加隐式字段。

## 现有契约的不足

现有 evidence 是非空 text 加单一 text/page/time 位置。它能验证最小文本链路，但不能完整表达工作表单元格、PPT 形状、图片区域、复合附件、表格结构和多条派生证据。因此首个多格式实现前必须升级契约，不能把 cell 坐标拼成文本或把 slide 序号偷装成 page 来假装支持。

## 建议的内部对象

| 对象 | 作用 | 需要保留的关系 |
| --- | --- | --- |
| SourceVersion | 不可变输入版本 | 调用方来源 ID、revision、原始摘要、媒体类型 |
| Artifact | 原件或派生文件/流 | 摘要、类型、父 artifact、转换器/版本/选项；引用不包含长期访问密钥 |
| ContentBlock | 段落、标题、表格、图片、转录或模型描述 | block ID、类型、顺序、父节点、内容及一个或多个 Locator |
| Locator | 位置的带类型表示 | artifact/来源引用、具体坐标、单位和精度 |
| Derivation | 抽帧、裁剪、旋转、转码、分段等派生 | 父子产物、时间/几何映射、转换参数与来源服务 |
| Coverage / Issue | 本次请求处理了什么、缺少什么 | 目标 profile、单元范围、completed/skipped/failed、原因 |
| ProviderInvocation | 可追溯的外部调用 | provider/model/config 版本、输入引用、usage、状态与原始响应引用 |

块可以没有 text，例如图片资源；表格应有行列/合并结构，Markdown 只是导出视图。记忆提取、向量化和 RAG 切块留给主仓；解析层仅按自然结构或资源上限分单元。

## 定位类型

| 类型 | 关键字段建议 | 语义 |
| --- | --- | --- |
| text_span | start/end、offset_unit、encoding_ref | 原文 code point 左闭右开；清洗后文本需映射 |
| page_region | page、bbox/polygon、coordinate_space | 页 1 起始；坐标原点/单位/尺寸/旋转全部明确 |
| slide_shape | slide_index、shape_id、可选区域 | 页与 slide 是不同类型；备注单独标注 |
| sheet_range | sheet_id/name、A1_range、可选行列索引 | 单元格范围闭区间语义独立于字符 span；表名可含空格/引号 |
| image_region | image/frame_id、区域与坐标系 | 映射回原图，保留 EXIF 方向/裁剪关系 |
| media_segment | stream_id、start_ms/end_ms、可选 frame_pts | 原始时间线，毫秒左闭右开；原生 PTS/timebase 保留用于精度追溯 |
| document_node | part/relationship、节点路径 | DOCX 原始结构；渲染页只定位到派生 PDF |
| structured_node | record_index、pointer/path、可选 text_span | JSON Pointer 或格式相关路径，不混用到原始字节偏移 |
| resource_node | 内部资源路径、DOM/章节/邮件 part | EPUB、网页和邮件的内容位置，携带快照/消息上下文 |
| archive_entry | entry_path、child_source_ref | 容器条目层级，可与子文件具体定位组合 |

不同定位可以组合，不能互相冒充。视频帧的 OCR 至少需要“原视频时间 + 帧图区域 + 抽帧派生关系”；一个归一化 page 字段无法承载它。

## 内容来源的区分

每个块记录获取方式：原生提取、OCR、ASR 或模型推断，并关联实际工具/服务版本。原文文本、纠错后的文本和描述分别保留，不以模型增强结果覆盖原始证据。输出置信度可选，不能因为缺省就写 1.0。

公式、单元格缓存和显示文本是不同值；转录、字幕与画面说明是不同证据；正文与备注是不同内容角色。这些区别必须在结构里表达，不能只靠 Markdown 文案解释。

## 版本迁移步骤

1. 先用 TXT、PDF、XLSX、PPTX、视频和附件组合各一个合成结果检验表达能力。
2. 定义新的版本化 Schema、兼容边界、错误/覆盖语义及正反例；增加显式活动版本配置，使检查工具能保留多个历史版本。
3. 给主仓增加新版本消费适配和回归；旧版投影只允许无损表达的内容，否则拒绝或显式声明损失。
4. 更新主仓快照、来源提交和摘要，再启用新版本输出。现有契约只允许 completed/partial/failed，不能提前向它写 planned/running 等任务状态。

新旧草案并存，主仓消费快照尚未迁移。本次只落地运行时需要的契约子集；每增加格式都要更新 schema、语义回归和消费兼容说明。
