# M3-A 自动验证执行记录

日期：2026-10-19；执行环境：Windows，仓库 .venv CPython 3.12.13；无文档组环境为 .local/m2-base-env。版本为当前未提交工作区，新文件及对应文档不属于已有 HEAD；本记录不代表 GitHub CI。

需求：[开发前 M3 需求](../changes/2026-10-19-m3-foundation-before.md)；残余风险：[开发后清单](../changes/2026-10-19-m3-foundation-after.md)。

| 命令/范围 | 实际结论 |
| --- | --- |
| unittest discover -s tests -v | 完整环境 108 项通过，90.098 秒；其中当时 M3 模块 18 项 |
| 后补累计预算及输入修改隔离测试，再定向运行 test_document_analysis.py | 当前 M3 模块 20 项通过；运行代码相对全量测试时未再修改 |
| 无 documents 基础环境定向运行 test_document_analysis.py | 相同 20 项通过，不需要引擎、模型或网络 |
| node --test tests/console_model.test.mjs | 4 项通过 |
| scripts/evaluate_m3.py | 显式 dry_run；页 1 成功/页 2 合成超时、partial；已知框 [60,160,300,320]、heading 上下文、2 次调用、total_tokens=null；原生结果未变 |
| scripts/audit_dependencies.py --api --documents | 安装闭包与锁审计通过，无禁止组件；锁 66 条包记录 |
| scripts/check.py、git diff --check | 收尾检查通过：194 个文件，链接/语法/契约/样例/catalog/源码导入边界；无空白错误 |
| python -m knoa_parse capabilities | 六种后缀仍仅 native_extract；外部能力仍只有已有 text_model；无文档分析目标或 mock 声明 |

锁 SHA256：`6f885ace1718a280a6bfb2d0481534ea550fbf09e18a7feb41dc278bb2c72fb3`，与变更前相同。

M3-01～11 的合成可执行分支已验证，测试代码见 tests/test_document_analysis.py；M3-12 的既有链路回归、依赖审计及文档/契约边界检查已完成。未勾选人工用例，不证明真实图片/服务/平台效果。

原始离线报告：`.local/m3-dry-run/report.json`，报告含 mock/dry_run 标记，不序列化输入 bytes。输入为人工写入的身份字节和预写响应，不是有效 PDF/栅格，也不评估 OCR 准确率。没有发送任何真实模型请求。

完整回归仅出现已有 Starlette TestClient/httpx 弃用提示，未为提示添加新依赖。真实跨平台、实际页图、计费及人工验收均未执行，按 after 文档保留未勾选。
