# 开发后不确定项：Knoa Parse 工作台 V2

2026-11-10 复验补充：本文件保留 11 月 5 日的历史结果；桌面三尺寸、键盘 tab/焦点、合成凭据和下载摘要已有新的真实浏览器证据，见 [review 修复记录](../records/2026-11-10-console-review.md)。不同 DPI、屏幕阅读器和真实复杂资料仍未验收，见 [当前不确定项](2026-11-10-console-review-after.md)。

日期/版本：2026-11-05；关联开发前需求：[2026-11-05-console-v2-before.md](2026-11-05-console-v2-before.md)；负责人：Knoa Parse。

## 已验证事实

已完成静态实现和自动验证：

- 继续使用静态 HTML/CSS/ES modules；没有新增 Node/npm、CDN、外部字体、Python 依赖、后端 API 或解析层导入。
- 三主视图保持不变；Inspector 增加只读诊断抽屉，展示任务事实、coverage/issues/artifact 数量、后端未提供的指标边界和最多 100 条前端同步事件。
- 诊断事件只保存在页面内存，统一做 Bearer/API key/token/secret 脱敏；不写 localStorage，不上传，不改变任务状态。
- 任务列表加入 `ul/li` 语义，诊断按钮具备 `aria-controls`/`aria-expanded`，关闭抽屉后回收焦点；保留现有 tab、dialog、live region 和减弱动画规则。
- `node --check src/knoa_parse/apps/console/static/app.js` 通过。
- `node --test tests/console_model.test.mjs`：5 项通过。
- `.venv\\Scripts\\python.exe -m unittest tests.test_console`：5 项通过。
- `.venv\\Scripts\\python.exe -m unittest discover -s tests -v`：224 项通过，2 项可选视频工具链测试跳过。
- `scripts/check.py`：301 个文件通过；依赖审计：69 条 lock 记录通过；`git diff --check` 通过。

自动检查不能代替浏览器视觉、键盘、Accessibility Tree、网络面板和真实复杂资料验收；这些项目仍保留在下方不确定项中。

## 不确定项

- [ ] ID：CONSOLE-V2-UNC-01；优先级：P1；关联目标：桌面三尺寸视觉验收。
  - 不确定内容及原因：本轮未完成 1440/1280/1024 浏览器截图、字体渲染、滚动层和不同 Windows 缩放比例检查；本机启动 Uvicorn 做浏览器检查时被 Windows 自动审批阻塞。
  - 风险：可能出现横向溢出、文字截断、Inspector 过窄或焦点不可见。
  - 前置条件/样本：Windows 浏览器、100% 缩放、脱敏合成任务。
  - 人工步骤：启动 console 与 worker，分别使用 1440×900、1280×800、1024×768 打开工作台，切换三视图并展开 Inspector/诊断抽屉。
  - 预期与判断标准：三个目标视口无横向溢出，任务和证据均可定位；已知限制单独记录。
  - 证据：待补充三种尺寸截图和浏览器控制台记录。
  - 处置：未完成前不宣称视觉验收通过。

- [ ] ID：CONSOLE-V2-UNC-02；优先级：P1；关联目标：无障碍语义。
  - 不确定内容及原因：自动测试不能完全替代键盘、焦点回收、屏幕阅读器和 Accessibility Tree 验证；本轮未完成浏览器人工操作。
  - 风险：任务选择、tab、dialog 或诊断抽屉可能无法被辅助技术理解。
  - 前置条件/样本：键盘-only 流程和浏览器 Accessibility Tree。
  - 人工步骤：验证跳过导航、Ctrl/⌘+K、任务选择、tab 切换、dialog、诊断抽屉和关闭后的焦点回收。
  - 预期与判断标准：焦点可见、操作可完成、状态变化可感知；未覆盖的浏览器组合列明限制。
  - 证据：待补充 Accessibility Tree 或操作记录。
  - 处置：未完成前不宣称无障碍验收通过。

- [ ] ID：CONSOLE-V2-UNC-03；优先级：P1；关联目标：模型密钥保护。
  - 不确定内容及原因：需要在真实浏览器网络面板、localStorage、DOM、诊断事件和错误路径中确认密钥不泄漏；本轮仅完成代码级脱敏测试和现有 Python 模型设置测试。
  - 风险：前端重构可能把凭据写入日志、状态快照或错误文本。
  - 前置条件/样本：合成 API Key，不使用真实凭据。
  - 人工步骤：读取、修改、保存、测试模型设置，检查网络面板、DOM、存储和诊断事件。
  - 预期与判断标准：页面、存储、事件和错误均不含完整或可恢复的 key。
  - 证据：待补充脱敏网络与存储检查。
  - 处置：未完成人工检查前不宣称密钥边界完成。

- [ ] ID：CONSOLE-V2-UNC-04；优先级：P1；关联目标：真实复杂结果展示。
  - 不确定内容及原因：自动测试难以覆盖真实大表格、重复定位、图片 artifact、超长 JSON 和不完整结果的组合布局；本轮未启动浏览器样本验收。
  - 风险：预览可能误导完整性，或截断/滚动行为影响调试判断。
  - 前置条件/样本：脱敏 DOCX/PPTX/XLSX/PDF 合成或授权样本及 SHA256。
  - 人工步骤：打开结果、滚动预览、下载原件/完整 JSON/artifact，并核对下载文件摘要。
  - 预期与判断标准：预览截断明确，完整 artifact 可下载，原始结果不被修改。
  - 证据：待补充截图、下载文件和摘要。
  - 处置：未完成真实样本验收前，复杂资料展示保持开发状态。

## 收尾结论

自动验证已完成，P0 的代码级边界和 Parse 隔离保持通过；P0/P1 浏览器人工验收、真实复杂结果和网络面板检查尚未完成，不能标记为全部通过。对应执行摘要：[2026-11-05-console-v2](../records/2026-11-05-console-v2.md)。
