# 0.2.0-draft.1：首个运行时证据契约

这是与旧版并存的新草案，当前实现文本/JSON 及初始原生文档路径。主仓消费快照仍为旧版，使用本版需要消费端显式迁移，不做有损自动投影。

[Schema](parse-result.schema.json) 从 [运行时模型](../../src/knoa_parse/core/models.py) 生成；执行 `python scripts/export_schema.py` 更新，检查工具验证无漂移。版本索引见 [index.json](../index.json)。

包含 Source、Artifact、ContentBlock、类型化定位、Coverage 和 Issue。定位明确原件/派生产物精度；结果不包含存储路径、长期访问密钥或上游类型。状态为 completed/partial/failed，独立于任务状态。

文本字符偏移以原件 UTF-8 解码后的 Unicode code point 计数，左闭右开；保留 BOM、CRLF 和 emoji，不做换行或编码清洗。JSON 根节点用空 JSON Pointer；保留原件，拒绝重复键和非有限值，初始深度/节点数受限。

运行时还校验唯一 ID、引用完整性、来源 artifact 摘要/大小、正向跨度与状态/缺口一致性。JSON Schema 无法单独表达这些跨字段条件，消费方需实施同等语义校验。当前仅声明已实现的对象；幻灯片形状、派生变换和 ProviderInvocation 等在相应能力落地时继续演进草案。

Office/原生 PDF 在已审计的 documents 组中启用。Word/PPT 的 document_node 定位到保留的上游 JSON 树；空 pointer 可以表示原始文档容器整体。Excel 原始字段用 sheet_range，PDF 区域用原件页码/点数。图片块 data.image_artifact_id 指向派生图片，完整上游树作为 engine_result 产物保存。媒体尚未启用。
