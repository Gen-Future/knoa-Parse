# 开发前测试需求：M3-C PDF 页图输入与几何映射

创建日期：2026-11-02；状态：实现前定义。范围：把 PDF 原生结果、人工/上游生成的整页栅格和 PDF 页规格绑定成 `PreparedPage`。本阶段不实现 PDF 渲染，不调用 OCR/文档服务，不接入 API/worker，不修改 ParseResult Schema 或能力清单。

## 目标与边界

输入必须同时提供：原生 PDF `ParseResult`、页号/MediaBox/旋转规格、整页正向栅格字节、栅格媒体类型和像素尺寸。输出包含派生页图 artifact、来源 Source 绑定、摘要、页号、源页尺寸和旋转后的 upright pt 尺寸。仅允许 PNG/JPEG；不接受裁切、局部截图、未知旋转或用户路径。

旋转 0/180 保持宽高，90/270 交换 upright 宽高。只比较物理宽高比，不猜 DPI；允许 2% 比例误差处理栅格取整。所有页先整体预检，任一错误都不返回部分列表。源页可以原生 coverage failed，但必须是存在的 PDF 页。artifact ID 不得与原结果或其他页冲突。

## 验收用例

- [ ] M3C-01 / P0：合法 PDF 页、PNG/JPEG、正向整页、源摘要正确生成 `PreparedPage`；artifact role=derived、大小/SHA 与字节一致。
- [ ] M3C-02 / P0：旋转 0/180/90/270 的 upright pt 宽高和映射字段正确；不把旋转后的宽高误写回源 MediaBox。
- [ ] M3C-03 / P0：栅格宽高比与旋转后源页宽高比在 2% 内通过，超出拒绝；不根据宽高比猜 DPI 或缩放坐标。
- [ ] M3C-04 / P0：Source ID/SHA/源 artifact、PDF media type、页号与 coverage 绑定；跨源、错摘要、非 PDF、未知页拒绝。
- [ ] M3C-05 / P0：零字节/不支持媒体/非正像素/非有限页尺寸/未知旋转/裁切标记拒绝；不把 JPEG 当 PNG。
- [ ] M3C-06 / P0：重复页、重复 raster artifact ID、与原始 artifact ID 冲突、规格与栅格页集合不一致时整批拒绝。
- [ ] M3C-07 / P1：页顺序乱序输入时输出按源页号排序；不同页独立摘要和尺寸不串绑。
- [ ] M3C-08 / P0：输出传入 M3-A 编排后，服务请求只携带对应页图和 media_type；原生 ParseResult 不被修改。
- [ ] M3C-09 / P1：派生 artifact 不包含原始 PDF 字节或用户路径；错误消息不包含图片内容。
- [ ] M3C-10 / P0：模块测试、M3 编排、全量回归、文档/契约边界和依赖审计通过；不新增运行依赖，OCR/document_understanding 仍未进入 capabilities。

自动测试使用固定字节的合成栅格和人工写入页规格，不证明 PDF 渲染效果。真实 PDF 页面尺寸、裁切、旋转、渲染质量及服务效果进入开发后 TODO。开发后记录：[M3-C after](2026-11-02-m3c-page-input-after.md)。
