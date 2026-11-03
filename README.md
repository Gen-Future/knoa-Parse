# Knoa Parse

把资料转换为可追溯的结构化证据，供 [Knoa](https://github.com/Gen-Future/Knoa) 或其他产品使用。

**当前支持文本、JSON 和初始原生文档解析。** 文档依赖组通过审计后开放 `.docx`、`.pptx`、`.xlsx`、`.pdf`，共享 CLI/API、任务和产物存储。外部文本模型已通过可插拔接口接入硅基流动，支持自定义 OpenAI/Anthropic 兼容平台及独立 CLI/API 调用；OCR、复杂版面、媒体和资料自动增强尚未接入。原生范围见 [实施记录](docs/implementation-status.md)，模型配置与测试见 [模型接入](docs/model-services.md)。

## 本地使用

目标 Python 3.12，兼容 Python 3.11。项目与可选依赖完整锁定在 [uv.lock](uv.lock)。初始化文档/API 环境：

```sh
uv sync --locked --extra api --extra documents
uv run --no-sync knoa-parse capabilities
uv run --no-sync knoa-parse parse contracts/v0.2.0-draft.1/examples/source.txt
```

只需要文本/JSON 时可以用 `uv sync --locked --extra api` 省去文档组；不装文档组就不会广告 Office/PDF 能力。当前机器也可以直接从已创建的环境运行：

```sh
.venv/bin/knoa-parse capabilities
.venv/bin/knoa-parse parse /absolute/path/to/report.xlsx
```

Windows PowerShell 可直接使用仓库环境：

```powershell
.\.venv\Scripts\python.exe -m knoa_parse capabilities
.\.venv\Scripts\python.exe -m knoa_parse parse "D:\资料\report.xlsx"
```

本次 Windows 自检及本机 uv 路径见 [Windows 自检记录](docs/windows-self-check.md)。

结果输出到 stdout；原件、任务与结果持久化在 `.local/knoa-parse`，可通过 `--data-dir` 指定位置。CLI parse 会输出 completed/partial 结果；退出码 0 表示完成、3 表示部分完成、2 表示失败。CLI 也提供 `status JOB_ID`、`result JOB_ID`、`cancel JOB_ID`、`worker --once` 和持续 `worker`。

当前为本地单用户 Demo，API 和工作台默认不鉴权，打开页面自动加载，无需访问令牌。项目服务配置见 [server.example.json](configs/server.example.json)，`.local/server.json` 只配置 `data_dir`；模型平台凭据单独在“模型服务”中设置。

从项目根目录启动独立 API：

```powershell
cd D:\develop\Knoa-Parse
.\.venv\Scripts\python.exe -m uvicorn knoa_parse.apps.api:create_from_env --factory --host 127.0.0.1 --port 8765
```

环境变量仍可覆盖本地设置；详细说明见 [模型与服务配置](docs/model-services.md)。

另一个终端运行 `uv run --no-sync knoa-parse worker`。API 提交任务后由 worker 执行，不依赖 Web 请求后台线程。

## 可选观测工作台

需要图形界面时，启动工作台入口（包含 API），使用同一项目配置：

```powershell
cd D:\develop\Knoa-Parse
.\.venv\Scripts\python.exe -m uvicorn knoa_parse.apps.console:create_from_env --factory --host 127.0.0.1 --port 8765
```

另一个终端从项目根目录运行 `.\.venv\Scripts\python.exe -m knoa_parse worker`，自动读取配置的数据目录。打开 [本地工作台](http://127.0.0.1:8765)，即可直接使用，无需登录。可查看实际任务状态、上传资料、筛选任务、检查内容/覆盖/定位及下载产物；左侧“模型服务”可选择硅基流动/自定义平台、OpenAI/Anthropic 协议，保存配置并测试连接。工作台 API 为 `/api/v1/...`；独立 API 为 `/v1/...`。

工作台使用无构建静态资源，不要求安装 Node/npm，不改解析管线、证据契约和原有预算。删除或不启动它不影响 API/CLI/worker。说明与启动方式见 [工作台模块](src/knoa_parse/apps/console/README.md)，决策见 [ADR 0005](docs/adr/0005-optional-observation-console.md)。

如需预览合成任务，可显式运行 `python scripts/seed_console.py`，仅向空的 `.local/console-preview/data` 创建真实解析任务。把 API/worker 的数据目录同时改为该路径即可；不会向正常工作目录自动塞入演示数据。

上传使用 `POST /v1/sources?filename=example.txt`，body 是原始文件字节；随后 `POST /v1/jobs` 提交 `source_id`、可选 `idempotency_key`。查询 `/v1/jobs/{id}`、`/v1/jobs/{id}/result`，取消 `/v1/jobs/{id}/cancel`，读取 `/v1/artifacts/{id}`。当前 Demo 数据接口无需 Authorization 请求头。目标能力只开放 `native_extract`。

通用观测接口：`GET /v1/jobs?limit=50` 返回最近任务（上限 100，items/has_more/limit），每项含原任务字段、created_at 和 source 元数据；`GET /v1/sources/{id}` 读取来源元数据。观测查询不领取任务，不暴露租约信息。

## 目录与边界

一个 Python 发行项目，源码与模块说明统一放在 `src/knoa_parse`：

```text
src/knoa_parse/
  core/             来源、证据模型、协议、探测、任务及产物存储
  parsers/          文本、JSON、DOCX/PPTX/XLSX/原生 PDF 等家族
  engines/          经审计的 Docling 无模型路径与可选依赖检查
  enrichment/       上下文与外部增强的职责边界
  processors/       非模型工具与有限原始字段补充
  providers/        外部模型能力边界
  apps/             CLI、API、worker 与具体实现装配
contracts/          新旧版本契约、索引与合成样例
evals/              格式验收与实施基线
testing/            开发前测试需求、开发后不确定项与人工验收记录模板
docs/               架构、实现方案、取舍及实施状态
scripts/ tests/     检查、引擎实验与回归
```

优先复用成熟项目的能力模块，默认只选一个通用文档引擎；按需接入媒体和正文提取模块。RAG-Anything 当前仅作设计参考。不引入本地模型、权重下载、RAG 存储或上游应用服务。

[格式 catalog](src/knoa_parse/parsers/catalog.json) 将家族规划与 `enabled_extensions` 分开，只有通过验收的后缀启用。源码导入边界由检查工具验证；Parser 不直接导入上游框架、供应商或其他资料家族。

## 验证与 Docling 实验

M3 已进入 [外部文档能力基础阶段](docs/m3-document-analysis.md)：同步单页接口、页级编排、上下文、预算、PDF 页图输入校验和 Renderer 边界可以离线验证，运行 `python scripts/evaluate_m3.py` 输出显式 dry-run 报告。尚未选择 PDF 渲染库或接入真实 OCR/文档服务，不能用于真实扫描识别，也未新增产品目标。

人工逐项验收从 [测试需求目录](testing/README.md) 开始。后续工程必须先定义开发前测试需求，结束时补充开发后不确定项；本轮清单包含原生解析、任务链路、工作台和模型设置，尚未人工验证的项目不视为通过。

```sh
uv run --no-sync python scripts/check.py
uv run --no-sync python scripts/audit_dependencies.py --api --documents
uv run --no-sync python -m unittest discover -s tests -v
```

以上也可在已具备项目及开发依赖的 Python 环境中直接执行。API 测试需要 api extra；纯基础环境会明确跳过这些测试。macOS 历史基线通过 51 项回归；Windows 迁移基线通过 53 项，M2 扩展后完整环境通过 60 项，基础/API 环境执行 46 项并跳过 14 项文档相关测试。CI 配置分别在 Linux/Windows 验证基础/API 与附加文档的环境，远端执行结果需另行确认。

Docling 固定为 2.139.0，只启用原生格式与 NativePdfPipeline；不选择模型、OCR、chunking、Serve、音视频等 extras。完整上游 JSON 与图片会保存成可读取的产物。DOCX/PPTX 定位指向派生树；PPT 的 EMU 不冒充 PDF 点数；Excel 同时保留公式、缓存、类型/格式、合并与隐藏字段。上游已提取的原生图表数据映射为 table，保留类别与数值；不会把重构图表单元格冒充原始 Excel 地址。PDF 保留页/区域，但不重建阅读顺序或表格；包含位图的页面保守返回 partial，即使存在原生页眉文字。

六种后缀另有 15 个预先编写语义预期的合成样例，覆盖复杂结构、定位、损坏和明确缺口。运行并保留结果/产物：

```sh
uv run --no-sync python scripts/evaluate_m2.py
```

Windows 也可用 `.\.venv\Scripts\python.exe scripts/evaluate_m2.py`。未装 documents 时，完整验收明确报 blocked；仅验证文本/JSON 可显式加 `--base-only`。样例与验收边界见 [M2 覆盖记录](evals/m2-coverage.md)。

可以生成合成资料、重复运行同一受控实验：

```sh
uv run --no-sync python evals/document_fixtures.py .local/fixtures
uv run --no-sync python scripts/docling_spike.py --input .local/fixtures/sample.docx
uv run --no-sync knoa-parse parse .local/fixtures/sample.xlsx
```

实验先审计依赖，再禁止联网与子进程，保存上游 JSON 和时间/RSS 观察。转换成功不代替语义及任务验收；实测与已知限制见 [文档基线](evals/baselines/2026-10-15-documents.json)。

## 契约与文档

- [0.2.0-draft.1](contracts/v0.2.0-draft.1/README.md)：当前输出版本；Schema 与运行时模型对齐，保留语义校验。
- [0.1.0-draft.1](contracts/v0.1.0-draft.1/README.md)：保留旧版回归。主仓消费快照尚未迁移，新版需要显式消费适配。
- [完整实现方案](docs/implementation-plan.md)、[架构](docs/architecture.md)、[实施进度](docs/implementation-status.md)。
- [待办与能力闸门](docs/TODO.md)：记录 OCR/真实服务/复杂资料等尚未开放事项，不能由 mock 或传输层测试替代。
- [横向选型](docs/research/2026-10-15-module-selection.md)、[接入决策](docs/adr/0004-selective-module-integration.md)、[验收计划](evals/README.md)。

项目许可证待确认，尚未添加 LICENSE；当前 wheel 仅作本地构建验证。
