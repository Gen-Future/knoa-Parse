# M3-C PDF 页图输入与几何映射执行记录

日期：2026-11-02；环境：Windows，仓库 .venv CPython 3.12.13；仅使用合成 ParseResult、页规格和固定字节，不调用网络、OCR、图像解码或本地模型。需求：[M3-C before](../changes/2026-11-02-m3c-page-input-before.md)；后续：[M3-C after](../changes/2026-11-02-m3c-page-input-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_pdf_page_inputs.py -v` | 9 项通过：摘要/媒体/来源、旋转、比例容差、整批预检、集合冲突、拒绝条件、排序和原结果隔离 |
| `python -m unittest discover -s tests -v` | 128 项通过（完整环境复验） |
| 真实 PDF 渲染 | 未执行；当前模块不渲染 |
| 真实 OCR/文档服务 | 未执行；不属于本阶段 |
| 新增依赖 | 0；仅使用标准库、Pydantic 和已有 core 模型 |
| 能力清单 | 未改变，仍仅开放六种 `native_extract` |

M3-C 的自动测试只证明输入绑定与几何元数据规则，不能证明字体、裁切、旋转显示、DPI、图像质量或识别效果。所有人工项目保持未勾选。
