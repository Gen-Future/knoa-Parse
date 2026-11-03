# 开发后不确定项：M3-D PDF 渲染器边界与资源预算

日期：2026-11-02；关联 [开发前需求](2026-11-02-m3d-renderer-boundary-before.md)、[执行记录](../records/2026-11-02-m3d-renderer-boundary.md)、[能力闸门](../../docs/TODO.md)。

## 已验证事实

固定合成 Renderer 验证了源字节摘要/大小、PDF 类型、页集合、重复页、页数/单页/总输出/像素预算、Renderer 输出交给 M3-C、异常脱敏、无路径输入和原生结果隔离。编排层只调用 Renderer 一次；没有新增依赖或能力清单项目。

## 不确定项与 TODO

- [ ] **M3D-UNC-01 / P0 / 渲染器选型**。比较 PDFium/pypdfium2 等非模型路径的许可证、二进制分发、字体、透明度、密码 PDF、Windows/macOS/Linux 行为和安装增量。选定前不要修改 documents extras。
- [ ] **M3D-UNC-02 / P0 / 真实页面一致性**。用至少 3 份去敏 PDF 对照阅读器、MediaBox/CropBox/Rotate、文本和位图，验证 full_page_upright、90/180/270 旋转和裁切语义；当前合成比率不能代替视觉核对。
- [ ] **M3D-UNC-03 / P0 / 进程与资源边界**。渲染器可能在调用内部占用内存或卡住；当前同步编排只传递预算，不能强制中断。必须在 worker 子进程边界验证超时、子进程终止、临时文件清理和 Windows 行为。
- [ ] **M3D-UNC-04 / P1 / 图像质量与费用**。定义 DPI、颜色、JPEG/PNG、透明背景和单页/总页图上限，比较外部服务识别效果与上传费用；不能从字节预算推断 OCR 质量。
- [ ] **M3D-UNC-05 / P1 / 大文档吞吐**。接近页数、像素和输出上限的真实 PDF 需要冷启动、峰值内存、等待时间和连续运行观察；尚未定义性能 SLO，不得把一次合成运行当作吞吐承诺。
- [ ] **M3D-UNC-06 / P0 / 产品接入**。真实 Renderer、原始页图 artifact、原生 coverage 合并和 document_understanding 新契约必须先完成，再接 Store/API/worker/console；当前仍不开放 OCR。

## 收尾结论

M3-D 只完成 Renderer 注入边界和资源预算，真实渲染库和视觉验证继续由 [docs/TODO.md](../../docs/TODO.md) 阻塞。人工资源不足时可先完成选型与许可证记录，不能把 ScriptedRenderer 当作 PDF 渲染实现。
