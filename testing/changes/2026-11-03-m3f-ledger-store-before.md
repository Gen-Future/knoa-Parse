# 开发前测试需求：M3-F Provider 账目 SQLite 持久化

创建日期：2026-11-03；状态：实现前定义。范围：将 M3-E `InvocationRecord` 持久化到现有 Store 的 SQLite 数据库；不接真实 Provider、不接 worker/API/console、不开放 OCR。

## 目标与边界

现有数据库初始化时幂等创建 invocation 表和 schema 版本标记；旧数据库打开时自动完成本地迁移。账目写入使用事务和 `(run_id, unit_id)` 唯一约束，重复同一完整记录幂等返回，冲突或非法状态返回稳定错误。读取返回经过 Pydantic 校验的 `InvocationRecord`，不返回原始 body、凭据、请求内容或远端响应内容。

状态迁移沿用 M3-E 规则：planned 可提交/取消，submitted/unknown 可完成/失败/取消，failed 只有显式满足恢复条件才可进入下一 attempt；succeeded/cancelled 不允许回退。数据库操作不改变现有 jobs/sources/artifacts 事务语义，也不改变 API 能力清单。

## 验收用例

- [ ] M3F-01 / P0：新数据库包含当前 schema 版本和 invocation 表；旧数据库仅有 sources/jobs/artifacts 时启动可完成一次幂等迁移。
- [ ] M3F-02 / P0：合法 InvocationRecord 写入/读取字节语义不变；ProviderJobRef、usage=0/null、unknown billing 保留。
- [ ] M3F-03 / P0：同一 `id` 和同一 body 重复写入幂等；同一 id 不同 body、同一 run/unit 不同 id、摘要冲突均拒绝。
- [ ] M3F-04 / P0：expected_state 不匹配时拒绝并保持旧记录；合法状态迁移提交在一个事务内完成。
- [ ] M3F-05 / P0：succeeded/cancelled 终态不可回退；failed attempt 不能减少；billing 从 known/unknown 不被写回 not_sent。
- [ ] M3F-06 / P1：按 run/state 读取稳定排序；不存在记录返回稳定 invocation_not_found；返回对象不含 secret/body/path 字段。
- [ ] M3F-07 / P0：两个 Store/线程同时写同一 run/unit，最多一个成功，另一个得到可解释冲突；数据库不损坏。
- [ ] M3F-08 / P1：read_only Store 可读取已迁移账目，不能执行写入迁移或修改；现有任务查询/结果读取不受影响。
- [ ] M3F-09 / P0：全量回归、数据库/契约检查和依赖审计通过；无新依赖、无 API 路由变化，OCR/document_understanding 仍未开放。

自动测试使用临时 SQLite，模拟旧 schema 和并发写入；不验证真实远端恢复或账单。开发后记录：[M3-F after](2026-11-03-m3f-ledger-store-after.md)。
