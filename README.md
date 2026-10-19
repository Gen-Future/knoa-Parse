# Knoa Parse

把资料转换为可追溯的结构化证据，供 [Knoa](https://github.com/Gen-Future/Knoa) 或其他产品使用。

**当前支持文本、JSON 和初始原生文档解析。** 文档依赖组通过审计后开放 `.docx`、`.pptx`、`.xlsx`、`.pdf`，共享 CLI/API、任务和产物存储。OCR、复杂版面、媒体及外部模型尚未接入；原生路径的具体范围见 [实施记录](docs/implementation-status.md)。

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

结果输出到 stdout；原件、任务与结果持久化在 `.local/knoa-parse`，可通过 `--data-dir` 指定位置。CLI parse 会输出 completed/partial 结果；退出码 0 表示完成、3 表示部分完成、2 表示失败。CLI 也提供 `status JOB_ID`、`result JOB_ID`、`cancel JOB_ID`、`worker --once` 和持续 `worker`。

API 需要非空 Bearer token，面向同一用户的本地实例；所有任务/原件/产物共享这一个授权域，尚不提供多租户隔离。启动时设置环境：

```sh
export KNOA_PARSE_API_TOKEN='替换为随机长令牌'
export KNOA_PARSE_DATA_DIR='.local/knoa-parse'
uv run --no-sync uvicorn knoa_parse.apps.api:create_from_env --factory --host 127.0.0.1 --port 8000
```

另一个终端运行 `uv run --no-sync knoa-parse worker`。API 提交任务后由 worker 执行，不依赖 Web 请求后台线程。

上传使用 `POST /v1/sources?filename=example.txt`，body 是原始文件字节；随后 `POST /v1/jobs` 提交 `source_id`、可选 `idempotency_key`。查询 `/v1/jobs/{id}`、`/v1/jobs/{id}/result`，取消 `/v1/jobs/{id}/cancel`，读取 `/v1/artifacts/{id}`。所有数据接口要求 `Authorization: Bearer ...`。目标能力只开放 `native_extract`。

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
docs/               架构、实现方案、取舍及实施状态
scripts/ tests/     检查、引擎实验与回归
```

优先复用成熟项目的能力模块，默认只选一个通用文档引擎；按需接入媒体和正文提取模块。RAG-Anything 当前仅作设计参考。不引入本地模型、权重下载、RAG 存储或上游应用服务。

[格式 catalog](src/knoa_parse/parsers/catalog.json) 将家族规划与 `enabled_extensions` 分开，只有通过验收的后缀启用。源码导入边界由检查工具验证；Parser 不直接导入上游框架、供应商或其他资料家族。

## 验证与 Docling 实验

```sh
uv run --no-sync python scripts/check.py
uv run --no-sync python scripts/audit_dependencies.py --api --documents
uv run --no-sync python -m unittest discover -s tests -v
```

以上也可在已具备项目及开发依赖的 Python 环境中直接执行。API 测试需要 api extra；纯基础环境会明确跳过这些测试。本机已在全新 Python 3.12.11 环境完成安装、审计和 51 项回归；CI 分别验证基础/API 与附加文档的环境。

Docling 固定为 2.139.0，只启用原生格式与 NativePdfPipeline；不选择模型、OCR、chunking、Serve、音视频等 extras。完整上游 JSON 与图片会保存成可读取的产物。DOCX/PPTX 定位指向派生树；PPT 的 EMU 不冒充 PDF 点数；Excel 同时保留公式、缓存、类型/格式、合并与隐藏字段；PDF 保留页/区域，但不重建阅读顺序或表格，图片型页面会明确报告文字缺口。

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
- [横向选型](docs/research/2026-10-15-module-selection.md)、[接入决策](docs/adr/0004-selective-module-integration.md)、[验收计划](evals/README.md)。

项目许可证待确认，尚未添加 LICENSE；当前 wheel 仅作本地构建验证。
