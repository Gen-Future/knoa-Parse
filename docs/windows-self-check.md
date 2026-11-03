# Windows 迁移自检

日期：2026-10-19。工作区 `D:\develop`，仓库 `Knoa-Parse` 和 `Knoa` 各自独立。此前 macOS 机器的环境和绝对路径不适用于本机。

## 上下文与方案

- 迁移包 MANIFEST 中的 11 个文件 SHA-256 全部匹配，包括可读消息、三段会话及历史数据库。只读取验证，没有重新导入或修改正在使用的聊天数据库。
- Parse 检出基线为 `51f6399`，主仓为 `be1712e`，与原电脑的提交记录一致。本机两仓均已有 `origin/main`；自检时远端直接访问出现连接重置，未独立确认实时远端状态。
- 最早引用的 ChatGPT“拆分记忆系统架构”正文不在迁移包中。现有仓库及本聊天足以恢复当前 Parse 方案，但不能承诺早期完整需求全部恢复。
- Knoa 负责记忆形成、纠偏、检索和长期整理；Parse 负责独立解析并输出可追溯证据。主仓目前只有架构、契约和检查工具。
- 当前依据 ADR 0004：一个精简 Docling 原生文档引擎；RAG-Anything 仅参考设计；按资料类型分流程，通过适配层复用成熟项目；模型、OCR、ASR 等走外部服务。没有因 Windows 迁移改变选型或放宽本地模型边界。
- 当前启用 TXT、JSON、DOCX、PPTX、XLSX、原生 PDF；Markdown/CSV 等仍待实现，不因实施计划列出目标就宣称支持。复杂 PDF、Provider、音视频、执行恢复仍是后续阶段。
- 主仓保留 `0.1.0-draft.1` 契约，文件摘要与 Parse 历史版本一致；Parse 当前输出 `0.2.0-draft.1`，消费迁移仍待显式实施。本轮没有修改契约快照。

## 环境

系统 PATH 中的 Python 3.10.4 不满足 Parse 和检查工具要求。Parse 使用仓库专属 Python 3.12.13 与 `.venv`；uv 0.10.10 安装在 `.local/tools/bin/uv.exe`。运行时、缓存和工具均留在忽略目录中。主仓另建 Python 3.11 检查环境。

使用原有 uv.lock 安装 API、documents 和开发依赖，没有更新依赖版本。Windows 按锁文件标记额外安装 colorama、pywin32、tzdata；这些平台差异不代表引入了第二套解析引擎或本地模型。

在 `D:\develop\Knoa-Parse` 的 PowerShell 中直接运行：

```powershell
.\.venv\Scripts\python.exe -m knoa_parse capabilities
.\.venv\Scripts\python.exe -m knoa_parse parse contracts/v0.2.0-draft.1/examples/source.txt
.\.venv\Scripts\python.exe scripts/check.py
.\.venv\Scripts\python.exe scripts/audit_dependencies.py --api --documents
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

需要重新同步依赖时，使用本机 uv，并保持缓存和受管解释器在本仓：

```powershell
$env:UV_CACHE_DIR = "$PWD\.cache\uv"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.local\python"
& .\.local\tools\bin\uv.exe sync --locked --python 3.12 --extra api --extra documents
```

API 与 worker 分别在两个终端启动，使用相同的数据目录；token 自行设置为随机长字符串：

```powershell
$env:KNOA_PARSE_API_TOKEN = '替换为随机长令牌'
$env:KNOA_PARSE_DATA_DIR = "$PWD\.local\knoa-parse"
.\.venv\Scripts\python.exe -m uvicorn knoa_parse.apps.api:create_from_env --factory --host 127.0.0.1 --port 8000
```

```powershell
$env:KNOA_PARSE_DATA_DIR = "$PWD\.local\knoa-parse"
.\.venv\Scripts\python.exe -m knoa_parse worker
```

## 实际故障与修复

1. 默认 GBK 解码导致契约及 catalog 检查失败：文件读取显式使用 UTF-8；CLI JSON 输出也固定 UTF-8，覆盖中文和 emoji。
2. 上传和结果发布在写句柄未关闭时重命名/删除临时文件，触发 WinError 32：关闭写句柄后再探测、发布和清理。
3. worker 无条件导入 POSIX resource，以及使用 killpg/SIGKILL：POSIX 保留文件上限和进程组终止；Windows 直接终止当前解析子进程并等待退出，取消/超时测试核对进程确已结束。
4. 两种平台均在写结果前检查 UTF-8 结果字节及派生产物的合计预算，父进程继续验证大小、摘要和租约。Windows 没有 POSIX 的 RLIMIT_FSIZE，应用层检查不是 OS 级磁盘隔离；未来允许媒体子进程时仍需另做进程树管理。
5. 原始 Docling 实验脚本无条件导入 resource：Windows 仍执行转换与网络/进程审计，峰值 RSS 未测量时明确记为 null。
6. 主仓摘要清单检查把反斜杠与清单中的正斜杠比较，误报文件集合不一致：检查路径统一为 POSIX 表示，摘要和契约本身不变。

## 验证范围

Windows Parse 完整回归通过 53 项，其中 12 项文档测试。新增两项覆盖传统代码页下的 CLI UTF-8 输出和结果写入预算；原有取消/超时测试增加子进程退出断言。四类原生文档受控实验均成功，没有推理模块加载或未解释的网络/进程尝试。

实际启动 uvicorn，通过回环 HTTP 完成 token 校验、上传、排队、独立 worker、结果读取和中文/emoji 原文核对；服务在验证后停止。主仓独立 Python 3.11 环境的文档检查和 12 项契约测试通过。

仓库检查、依赖安装闭包与锁文件审计继续执行；机器可读依据保存在 [Windows 基线](../evals/baselines/2026-10-19-windows.json)。CI 增加 Windows/Linux 双平台与两个可选组的矩阵，尚未在本轮推送后观察远端执行。

这些是合成资料和本机行为验证。复杂中文真实资料、macOS/Linux 本轮改动后的重跑、生产隔离、许可证及主仓契约迁移仍需各自验收。旧 macOS 基线保留，不用 Windows 成绩改写历史。
