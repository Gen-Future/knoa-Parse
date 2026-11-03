# 外部文本模型接入

已实现 core 的 `TextModelProvider` 接口与 OpenAI Chat Completions、Anthropic Messages 两种兼容协议适配器，首个配置为硅基流动 `deepseek-ai/DeepSeek-V3.2`。使用 Python 标准库，没有新增依赖或本地推理。

当前开放独立的同步文本生成 CLI/API。原生解析任务与 worker 仍只执行 `native_extract`，保留禁网检查，不自动发送资料。OCR、视觉、ASR、embedding、reranker、流式输出及资料自动增强尚未开放。响应带 `acquisition: inferred`，不写入 ParseResult；后续资料增强目标需先升级证据契约与验收。

## 私密配置

从仓库根目录运行。复制 [配置样例](../configs/providers.example.json) 至 `.local/providers.json`，在本地填写 key；`.local/` 已被 Git 忽略。不要把真实 key 写入样例。API token 与供应商 key 是独立凭据。

服务配置位于 `.local/server.json`，样例见 [server.example.json](../configs/server.example.json)，目前只需 `data_dir`，默认 `.local/knoa-parse`。API、console、CLI 和 worker 从同一配置读取数据目录。

当前本地单用户 Demo 默认免鉴权：页面自动加载，不需要工作台 token；旧配置的 api_token 与 KNOA_PARSE_API_TOKEN 不再用于启动鉴权。模型平台 API Key 继续保存在私密模型配置中，不回显给页面。

可用 `KNOA_PARSE_SERVER_CONFIG` 指定服务配置路径，`KNOA_PARSE_DATA_DIR` 可选覆盖数据目录。从项目根目录运行，配置中的相对路径按当前工作目录解析。

可通过 `KNOA_PARSE_PROVIDER_CONFIG` 指向私密 JSON 文件的绝对路径，供其他工作目录或多个进程复用。显式路径不存在或配置错误会安全失败；既无默认文件也无环境配置时，不启用该能力。

环境变量覆盖文件中相应字段：

| 环境变量 | 含义 |
| --- | --- |
| KNOA_PARSE_MODEL_PROVIDER | 平台标识，可自定义名称，默认 `siliconflow` |
| KNOA_PARSE_MODEL_PROTOCOL | `openai` 或 `anthropic`，默认 `openai` |
| KNOA_PARSE_MODEL_ANTHROPIC_VERSION | Messages API 版本，默认 `2023-06-01` |
| KNOA_PARSE_MODEL_BASE_URL | HTTPS 根地址，包含 `/v1` 等前缀，不含 `/chat/completions` |
| KNOA_PARSE_MODEL_MODEL | 供应商模型 ID |
| KNOA_PARSE_MODEL_API_KEY | 供应商 key |
| KNOA_PARSE_MODEL_TIMEOUT_SECONDS | 单次网络操作超时，默认 60 秒，最大 300 秒 |
| KNOA_PARSE_MODEL_ENABLE_THINKING | JSON 值 `true`、`false` 或 `null`，null 时不发送 |

硅基流动默认使用 `protocol: openai`，可省略 base_url、model、enable_thinking，采用样例默认值。`provider` 是平台名称，`protocol` 决定请求格式，两者独立。自定义平台必须填写 base_url、model 和 api_key；旧版 `provider: anthropic_compatible` 未指定协议时按 anthropic 解析。凭据仅在配置装配和传输内部使用，不写入任务数据库、能力声明或响应。

## CLI

```powershell
.\.venv\Scripts\python.exe -m knoa_parse capabilities
.\.venv\Scripts\python.exe -m knoa_parse model-check
.\.venv\Scripts\python.exe -m knoa_parse model-text .\contracts\v0.2.0-draft.1\examples\source.txt --max-tokens 256
```

`capabilities` 只报告配置，不联网，不保证账户余额。`model-check` 发送固定合成提示，要求返回 OK，输出最多 16 tokens。`model-text` 读取 UTF-8 文件，最多 128000 字节；prompt 上限 32000 字符，system 上限 4000 字符。

响应包括供应商、实际返回模型 ID、文本、结束原因、请求 ID（若有）与供应商报告的 token 用量。缺少用量时为 null，不估算费用。

## API

API/console 的 `create_from_env` 在启动时读取配置。通过工作台保存模型设置后，当前 API 立即切换；直接编辑配置文件仍需重启服务。独立 CLI 下次调用会读取新配置。独立 API 为 `POST /v1/models/text`，console 下为 `POST /api/v1/models/text`，当前 Demo 无需工作台访问令牌。工作台左侧“模型服务”可选择平台和协议、修改地址/模型/密钥、保存并测试连接。

```powershell
.\.venv\Scripts\python.exe -m uvicorn knoa_parse.apps.api:create_from_env --factory --host 127.0.0.1 --port 8765
```

另一个 PowerShell 终端可直接调用：

```powershell
$body = @{ prompt = 'Reply with exactly OK.'; max_tokens = 16 } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/v1/models/text' -Method Post -ContentType 'application/json; charset=utf-8' -Body $body
```

只接受 `prompt`、可选 `system` 与 `max_tokens`（默认 1024，最大 4096，受配置进一步限制）。body 上限 192 KiB，不接受用户提交供应商地址、key 或模型路由。同步返回，不进入解析任务队列。应用可用 `create_app(settings, token, text_provider=...)` 注入其他实现。

## 切换平台

可直接修改 `.local/providers.json`，或用 `KNOA_PARSE_PROVIDER_CONFIG` 选择其他私密配置。OpenAI 兼容平台示例：

```json
{
  "provider": "custom-platform",
  "protocol": "openai",
  "base_url": "https://your-provider.example/v1",
  "model": "your-model-id",
  "api_key": "REPLACE_WITH_YOUR_KEY"
}
```

Anthropic 兼容平台使用相同字段，将 `protocol` 设为 `anthropic`；配置样例见 [Anthropic](../configs/providers.anthropic.example.json) 和 [OpenAI](../configs/providers.openai.example.json)。`base_url` 均填写包含版本前缀的根地址，如 `https://your-provider.example/v1`，不要填写完整端点。

OpenAI 协议发送 Bearer 鉴权和 `/chat/completions`；Anthropic 协议发送 `x-api-key`、`anthropic-version` 和 `/messages`，system 使用顶层字段。后者合并 text 内容块，保留模型 ID、请求 ID，将 end_turn/stop_sequence 归一化为 stop；max_tokens/tool_use/refusal 不冒充完整答案。输入 token 包含供应商报告的缓存写入/读取用量。结构参考 [官方 Messages 文档](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)。

建议整体替换平台配置，Anthropic 协议应删除 enable_thinking 或设为 null，避免沿用硅基流动的专属字段。两种适配器均实现同一 core 接口，parsers 无需变更。其他协议后续可在 providers/text_model 实现，由 apps 装配。

每次请求只发送一次，不自动回退。429/5xx/网络故障返回 `retryable`，超时计费状态可能未知。401/402/403/404 有稳定错误代码；不回显供应商原始错误。坏 JSON、超大响应、截断或缺少文本不会报告成功。只允许 HTTPS，禁止重定向转发凭据。网络超时是连接/读操作超时，不承诺端到端总时限或取消远端计费。

参考硅基流动官方 [Chat Completions](https://docs.siliconflow.cn/docs/api/chat-completions-post)。代金券与模型可用性以账户实际响应为准。

## 验证

`tests/test_model_services.py` 使用合成响应验证平台切换、请求映射、用量、鉴权、限额、异常脱敏、超时和无自动重试。真实调用显式执行 `model-check`，不纳入常规测试或 CI。Anthropic 协议目前通过合成响应验证，未配置真实 Anthropic 账户进行联网测试。

## 工作台模型渠道设置

打开工作台会自动读取当前实例，直接点击左侧“模型服务”：默认展示硅基流动及已配置密钥的状态，密钥永不回显。选择自定义平台后可选 OpenAI 或 Anthropic 协议，并填写平台名称、HTTPS 根地址、模型和密钥。

“保存设置”将配置原子写入当前私密 provider 配置文件，替换当前 API 进程内适配器，无需重启；写入失败时保留原有配置和适配器。同一平台/协议/地址留空密钥可保留已有 key；渠道或地址变化必须输入对应密钥，不把旧凭据发送给新渠道。环境变量覆盖模型配置时，界面只读，避免保存后被覆盖而误认为生效。

“测试已保存配置”只测试已保存渠道，发送固定的最多 16 输出 tokens 的合成提示，明确消耗平台额度；有未保存修改时禁用。界面展示实际响应、模型和供应商报告用量，不自动重试。新接口为 `GET/PUT /v1/settings/model` 与 `POST /v1/settings/model/test`；工作台下加 `/api` 前缀，当前本地 Demo 无需鉴权。请求校验错误不回显提交的密钥。

当前按单 API 进程运行；多个 API 进程各自持有适配器时需统一重载。已有原生 worker 不使用模型配置，不因设置页面变化调用模型。
