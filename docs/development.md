# 开发指南

## 本地检查

本仓可独立检出，不要求相邻目录存在 Knoa。目标使用 Python 3.12，兼容 Python 3.11；运行与检查共享 pyproject.toml：

先运行 `python3 --version`；若解析到 macOS 自带的 Python 3.9，请选择 3.11+ 解释器。推荐联网环境按 README 使用 uv；手动创建虚拟环境时也需要安装项目及所需 extras，避免只安装旧检查依赖后运行新代码。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-check.txt
.venv/bin/python -m pip install -e '.[api]' httpx==0.28.1 packaging==26.1
.venv/bin/python scripts/check.py
.venv/bin/python -m unittest discover -s tests -v
git diff --check
```

检查覆盖文本规范、简单 Markdown 相对文件链接、JSON/YAML 语法、Schema 合法性、示例结构及定位语义，以及家族 catalog 的目录、扩展名归属、工具/Provider 声明与禁止本地模型的声明规则，以及源码导入边界。安装依赖闭包另由 scripts/audit_dependencies.py 检查；真实格式能力由运行时测试和引擎实验验证。

CI 的 push 与 pull_request 配置调用相同检查；远端需首次推送后确认运行情况。Actions 用法参考 [checkout](https://github.com/actions/checkout) 和 [setup-python](https://github.com/actions/setup-python)。

## 契约协作

变更首先在本仓完成。修改字段时更新草案版本、语义说明、样例与回归，再由 Knoa 显式更新消费快照。不要在主仓直接修复本仓契约副本，不要依赖 `../Knoa` 路径运行产品。

当前 `v0.1.0-draft.1` 为共同初始化草案，尚无发布标签；不能当作稳定兼容承诺。

多格式设计见 [结果模型](result-model.md)。contracts/index.json 索引新旧版本；当前 Schema 从运行时模型生成，检查工具验证漂移并保留旧版回归。

## 增加资料家族或依赖

先更新 [家族清单](../src/knoa_parse/parsers/catalog.json) 和对应目录说明，写明格式、位置模型、流程、可复用项目模块及验收案例。解析器只使用 core 的转换/增强/工具/Provider 接口；app 装配具体适配器。catalog 将家族规划和 enabled_extensions 分开，编译期已验收六种后缀；运行时还检查文档依赖组是否可用；检查工具核对实际能力清单。

按 [接入边界决策](adr/0004-selective-module-integration.md) 优先研究成熟项目模块。采用源码时记录上游固定提交、路径、许可、改动与测试来源；直接依赖锁定版本并验证上游输出到 Knoa 输出的结构损失。依赖或代码抽取尚未通过实验时不得标记为已集成。

安装依赖前检查其传递依赖与默认执行路径；不能仅通过包名或“已关闭 OCR”认定没有本地模型。不得安装本地权重、推理框架或自动模型下载工具。真实支持上线时同步更新声明校验和验收依据。

## Git

默认分支 `main`。提交说明使用中文，例如 `docs: 初始化解析仓库与证据契约草案`。推送前检查远端是否新增历史，禁止强推覆盖。

运行与验证命令见 [README](../README.md)，已知阻塞与尚未完成的验收见 [实施记录](implementation-status.md)。

依赖变更先更新并审核 uv.lock；日常运行 `uv sync --locked` 或 `uv run --no-sync`，避免运行中隐式改变可选组。文档验收用 `--extra api --extra documents`，基础环境测试会跳过文档实验。
