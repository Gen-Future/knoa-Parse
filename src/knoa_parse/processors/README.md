# 非模型工具适配

封装成熟库/命令的输入、输出、版本、超时与资源控制，不重新实现它们的底层算法。

| 目录 | 范围 |
| --- | --- |
| [media](media/README.md) | 音视频探测、转码、抽帧、音轨及图像基础处理 |
| [pdf](pdf/README.md) | PDF 原生文本/几何读取和渲染 |
| [office](office/README.md) | Office 原生读取及可选转换/渲染 |
| [markup](markup/README.md) | 编码、标记、DOM、结构化文本和 MIME 基础工具 |
| [containers](containers/README.md) | 受限容器读取和解包 |

只依赖 core 接口和非模型工具，不依赖业务解析器或 providers。不以“运行在 CPU”判定合规；本地训练模型、权重、推理引擎和首次使用下载均不允许。具体库均待选型。
