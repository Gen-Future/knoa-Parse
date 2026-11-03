# M3-D PDF 渲染器边界与资源预算执行记录

日期：2026-11-02；环境：Windows，仓库 .venv CPython 3.12.13；使用合成 PDF Source 元数据和固定 Renderer，无真实 PDF 渲染、无网络、无 OCR、无模型。需求：[M3-D before](../changes/2026-11-02-m3d-renderer-boundary-before.md)；后续：[M3-D after](../changes/2026-11-02-m3d-renderer-boundary-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_pdf_rendering.py -v` | 6 项通过：源校验、页预检、预算原子性、Renderer 输出形状、异常脱敏和路径隔离 |
| `python -m unittest discover -s tests -v` | 134 项通过（完整环境复验） |
| 真实渲染库 | 未执行；尚未选择 PDFium/pypdfium2 等方案 |
| 真实 PDF/字体/旋转/裁切 | 未执行 |
| 新增依赖 | 0；使用现有 core/Pydantic 和 M3-C 校验 |
| 能力清单 | 未改变，仍仅开放六种 `native_extract` |

这批自动测试只证明编排边界和预算检查，不证明 Renderer 可以正确绘制 PDF，也不证明进程级超时或峰值内存已被控制。人工项目保持未勾选。
