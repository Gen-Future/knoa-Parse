# M4-C 场景候选与时间关联执行记录

日期：2026-11-04；环境：Windows，仓库 `.venv` CPython 3.12.13。需求：[M4-C before](../changes/2026-11-04-m4c-scene-timeline-before.md)；不确定项：[M4-C after](../changes/2026-11-04-m4c-scene-timeline-after.md)。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p test_scene_detection.py -v` | 6 项通过：VFR PTS、最短场景、覆盖缺口、空样本、证据关联和重复 ID |
| PySceneDetect/真实视频 | 未执行；变化分数与帧样本为显式合成输入 |
| 新增依赖 | 0；仅实现时间线规则和区间关联 |
| 视频理解/产品路由 | 未注册，`video_understanding` 仍未开放 |

自动测试不证明镜头检测准确率、采样覆盖真实质量、音画同步或语义理解。
