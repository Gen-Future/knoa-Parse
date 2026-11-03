# M3-G Provider 调用生命周期协调器执行记录

日期：2026-11-03；环境：Windows，仓库 .venv CPython 3.12.13；无网络、无真实 Provider、无 worker/API 调用。需求：[M3-G before](../changes/2026-11-03-m3g-invocation-coordinator-before.md)；后续：[M3-G after](../changes/2026-11-03-m3g-invocation-coordinator-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_invocation_coordinator.py -v` | 5 项通过：计划原子性、提交/成功/失败/unknown/取消、显式 retry 和恢复查询 |
| 完整回归 | 待本阶段收尾后填写 |
| 真实 Provider/worker | 未执行 |
| 新增依赖/API | 预期均为 0；Coordinator 只使用 core Store |

本记录只接受合成账目和 artifact ID，不把它们当作真实解析结果。
