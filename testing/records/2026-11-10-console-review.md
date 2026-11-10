# 工作台 review 修复验证

日期：2026-11-10。依据：[开发前需求](../changes/2026-11-10-console-review-before.md)，[开发后不确定项](../changes/2026-11-10-console-review-after.md)。基线：`44ea194`。

## 问题与修复

| 问题 | 修复与回归判据 |
| --- | --- |
| 1024px 下双栏固定最小宽度溢出 | 双栏可收缩，工具栏换行；三种桌面视口的 document 宽度不超过 viewport |
| 轮询替换 DOM 丢失焦点、滚动与旧触发器 | 保留相同控件身份/滚动，HTML 无变化时不替换；当前触发器焦点回收与 Esc 关闭 |
| quoted JSON 凭据可进入诊断 | 事件只接收固定摘要/HTTP 状态，不保存任意错误正文与文件名；字段/条数硬上限和纵深脱敏 |
| 重连丢诊断、慢请求污染新会话 | 重连保留页面历史，重载清空；旧会话结果、刷新、上传和图片响应隔离，同结果请求合并 |
| 当前任务滑出最近窗口消失 | 保留选中任务快照，按任务 ID 读取真实状态 |
| 模型草稿切页丢失、只读配置仍可编辑 | 保留 dirty 草稿，显式重读才放弃；不可写时禁用表单 |
| 缺失来源阻断任务、partial 流程绿勾 | 来源失败单独提示，仍可查看任务；仅 succeeded 的处理步骤显示成功，发布结果与解析成功分开 |
| artifact ID 只见截断、覆盖缺口关联不直观 | 显示完整 ID/复制/下载，定位带 artifact ID，coverage 显示 issue_codes |

## 自动验证

- Node 语法检查与 7 项纯函数测试通过。
- Python console/模型设置专项：16 项通过。
- 依赖审计：69 条 lock 记录通过，无新依赖或禁止项。
- 完整 Python 回归：224 项运行，2 项可选视频工具链跳过，其余通过；未出现失败。视频工具链跳过与本次 UI 修复无关。
- 仓库文档/源码/契约检查：306 文件通过；`git diff --check` 通过。
- Edge 156.0.4314.58 / Playwright 1.62.1：19 个行为场景通过；Node 共报告 20 项（含父测试），0 skip、0 fail，无浏览器 pageerror。

## 浏览器执行

使用本机 Edge、隔离浏览器上下文、本地 fixture 服务。只加载当前静态界面；API 为合成响应且外网被阻断，不读取 `.local/providers.json` 等真实配置。测试工具是可选开发环境，不加入运行依赖、锁文件或默认部署。

运行方式（PowerShell；已安装工具的绝对路径按本机设置）：

```powershell
$env:KNOA_PLAYWRIGHT_MODULE = '已安装的 playwright 模块目录'
$env:KNOA_BROWSER_EXECUTABLE = '已安装的浏览器可执行文件'
$env:KNOA_CONSOLE_SCREENSHOTS = '1'
node --test tests/console_browser.test.cjs
```

未安装 Playwright 时该专项明确 skip，不影响无 Node 的 API/CLI/worker。截图保留在 Git 忽略的 `.local/manual-testing/console-review/`，仅包含合成资料。真实复杂样本、不同 DPI 与屏幕阅读器等限制见 after。

## 需求结论

| 需求 | 本轮结论 |
| --- | --- |
| CR-01 布局 | 1440/1280/1024 三视图无横向溢出；9 张视口截图与 1 张诊断视口截图保存并检查 |
| CR-02 焦点/语义 | task/tab/诊断按钮的焦点、日志滚动、Esc 和关闭回收通过真实 DOM 验证；屏幕阅读器读出未验证 |
| CR-03 日志 | quoted JSON/空格/header/URL 凭据、任意错误正文不进入诊断；数量/字段上限通过纯函数测试 |
| CR-04 会话 | 重连保留历史、reload 清空、重复结果请求合并；延迟旧结果/列表/图片隔离通过 |
| CR-05 任务窗口/来源 | 来源 404 仍可打开任务；选中任务移出窗口后按 ID 持续读取通过 |
| CR-06 状态/产物/设置 | 六状态、产物完整 ID 复制与下载 SHA256、只读配置和切页草稿保留通过 |

截图仅为合成场景的桌面布局证据；没有以它宣称复杂文档解析效果或跨浏览器/DPI 已验收。
