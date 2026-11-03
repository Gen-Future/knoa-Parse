# PDF 工具

状态：已实现 M3-C 页图输入与几何前置校验（`page_inputs.py`）及 M3-D Renderer 注入/预算边界（`rendering.py`）；PDF 原生页渲染仍未实现，不能据此开放 OCR。

原生 PDF 文本/几何读取与页面渲染。当前只校验调用方提供的 full_page_upright PNG/JPEG、页尺寸、旋转和来源摘要；候选 pypdf、pdfplumber、PDFium 等渲染路径仍需许可证、资源和真实样本验证。

返回页、坐标、原生对象与渲染关系；不把图像 OCR 伪装为普通文本读取。M3-C 不解码、不渲染、不访问用户路径。

只依赖 core 接口及审核后的非模型工具。由 apps 注入解析流程；不得调用 providers 或加载推理模型。Renderer 只接收固定 Source 字节和页规格，不接任意路径；预算检查不等于进程级沙箱。CPU/GPU 计算本身不是判断标准，是否包含学习模型及权重才是边界。

详细来源见 [调研](../../../../docs/research/2026-10-14-parser-landscape.md)。安装时锁定版本并验证二进制、传递依赖、退出码、资源限制和首次运行行为。
