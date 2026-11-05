# 可选解析工作台

这是独立的展示与操作入口，只通过现有Demo API 读取任务/证据、上传原件、提交任务、请求取消和下载产物。不实现解析，不直接访问 Store，不启动 worker，也不依赖主仓。模型渠道设置通过Demo API 读取脱敏配置、保存私密配置并测试已保存渠道。

界面使用 HTML/CSS/原生 ES modules，静态文件随 wheel 提供；没有 Node/npm 运行依赖、前端构建步骤、CDN、外部字体或新增 Python 分发。API 与 CLI/worker 不导入本模块。删除本目录及其 package-data 配置后，独立 API、CLI、worker 仍可工作。

## 运行

在已安装 api extra 的环境中，将数据目录配置在项目的 `.local/server.json`，从项目根目录运行（详见 [配置说明](../../../../docs/model-services.md)）：

```sh
python -m uvicorn knoa_parse.apps.console:create_from_env --factory --host 127.0.0.1 --port 8765
```

Windows 使用 `.\.venv\Scripts\python.exe`。另一个终端保持同一数据目录，运行 `python -m knoa_parse worker`。浏览器打开实例根地址即可直接使用，无需登录；访问 `/api/v1/...` 的仍是原有Demo API。独立 API 继续使用 `knoa_parse.apps.api:create_from_env` 和原 `/v1/...` 路径。

## 能力与边界

- 读取最近最多 100 项任务，包含 CLI 或其他入口创建的任务；统计明确限制在该返回列表内。按完整 ID 可打开更早任务。
- 展示实际 queued/running/succeeded/partial/failed/cancelled，不猜测未上报的细分阶段、完成百分比、执行耗时或 worker 心跳。
- 证据区展示原生内容、表格跨度、图表数据、公式/缓存、图片、原件/派生定位、覆盖与问题、完整结果及产物下载。
- 浏览器预览表格和大结果有显示上限；完整产物不因展示截断而修改。JSON/文本按纯文本转义，图片只内嵌预览 PNG/JPEG/GIF/WebP；不执行文件中的 HTML、公式或脚本。
- 工作台 V2 以桌面 1440/1280/1024 为主要验收尺寸，保留解析工作台、能力清单、模型服务三个主视图；任务 Inspector 内的诊断抽屉只展示任务事实、证据链和最近 100 条前端同步事件，不伪造后端阶段、耗时、费用或心跳。
- 诊断事件只保存在当前页面内存并做凭据脱敏；它不会写入浏览器存储、上传到 API 或改变任务状态。删除本目录后，API、CLI 和 worker 仍可独立运行。
- 单用户 Demo 默认不鉴权，不提供 token 输入框；页面启动自动加载任务和模型配置。模型平台 API Key 不回显、不写浏览器存储。
- 单用户实例授权边界与后端一致，不新增多租户承诺。默认仅绑定回环地址。

设计与准入依据见 [ADR 0005](../../../../docs/adr/0005-optional-observation-console.md)。

模型服务页面无需工作台登录：默认硅基流动，支持自定义平台、OpenAI/Anthropic 协议、地址/模型/密钥配置。密钥不回显；同一渠道留空保留，更换渠道必须输入新密钥。保存立即更新当前 API，连接测试使用平台额度；有未保存修改时不能测试。环境变量覆盖时只读，详见 [模型设置](../../../../docs/model-services.md)。
