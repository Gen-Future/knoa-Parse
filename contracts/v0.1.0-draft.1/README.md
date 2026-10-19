# ParseResult 契约草案

版本：`0.1.0-draft.1`。状态：未发布、可修改；属于本次启动建议，不是历史已定的字段协议。Schema 使用 [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core)。

文件：[Schema](parse-result.schema.json)、[成功示例](examples/success.json)、[失败示例](examples/failed.json)、[示例原文](examples/source.txt)。样例全部合成，不含真实用户资料。

## 顶层字段

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 精确匹配消费端支持的契约版本 |
| `parse_id` | 本次解析结果标识；重新解析产生新标识 |
| `source` | 调用方确定的 source_id、revision、原始字节 SHA-256、media_type |
| `parser` | 解析器名称和版本，用于回溯 |
| `status` | `completed`、`partial` 或 `failed`，这里只表达最终结果，不表达队列状态 |
| `evidence` | 证据数组，每项含结果内唯一 ID、text 与一个定位对象 |
| `errors` | 错误数组：稳定 code、可展示 message 和 retryable 建议；message 不含秘密 |

completed 的 errors 必须为空，evidence 允许为空（例如空文件）；partial 必须同时有 evidence 和 errors；failed 必须有 errors 且无 evidence。消费方不得把 partial 静默当作完整资料，也不能仅凭 completed 推断有可写入的记忆。

## 位置语义

每条 evidence 在草案中只有一种定位方式：

| kind | 必填字段 | 单位与约定 |
| --- | --- | --- |
| `text` | `start`、`end` | 解码后、未归一化原文的 Unicode code point 偏移，0 起始，左闭右开；不是 UTF-8 字节或 UTF-16 code unit |
| `page` | `page` | 来源文档页码，1 起始；草案不支持 bbox |
| `time` | `start_ms`、`end_ms` | 原始媒体时间线毫秒，0 起始，左闭右开 |

text 和 time 的 end 必须大于 start；Schema 无法表达字段间大小比较，由检查与未来导入器补充。evidence ID 只保证结果内唯一；建议消费者保留 `(source_id, revision, parse_id, evidence_id)` 完整引用。

文本示例约定 UTF-8 解码且保留 LF。生产环境处理其他编码、OCR 修正、表格、版面和复合定位前须扩展契约，不应把处理后文本偏移冒充原始位置。page/time 证据 text 可以是 OCR/转录结果，不声称与原始字节完全相同。

## 边界与兼容

- 不携带权威 workspace/tenant 授权信息；调用方自己绑定任务与来源，Knoa 导入时校验。
- 不包含记忆价值、画像、结论或长期记忆 ID。
- 未定义上传地址、原始文件持久化、HTTP 路由、流式传输、超时或任务轮询。
- `additionalProperties: false` 用于在草案联调中尽早发现字段漂移。新增字段也需新版本和消费者更新；不要假设任意新增字段都兼容。
- 不通过 `$id` 伪造可下载的发布地址。正式发版后再指定稳定的 Schema URI 与兼容策略。

Schema 只校验结构。来源摘要是否匹配实际输入、定位是否越界、页面是否存在、来源是否授权和 ID 是否与任务匹配，仍由执行与导入边界验证。检查工具仅对仓库内的合成文本样例核对摘要和字符定位。
