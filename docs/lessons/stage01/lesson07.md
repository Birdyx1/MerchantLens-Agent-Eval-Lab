# 1.7 运行版本清单

状态：已通过（清单由教师协助修改，控制变量回答正确）。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：30—45 分钟，包含练习和评审。

## 知识点

Trace 记录运行中发生的事；运行清单（manifest）记录该次运行使用的配置版本。比较两次表现时，需要知道模型、Harness、工具或数据是否变化。

PawBench 将模型和 Harness 作为两个评测维度；本课记录这些维度，为后续控制变量实验做准备。[PawBench 官方仓库](https://github.com/agentscope-ai/PawBench)

清单字段和模拟版本名称属于本项目练习约定，不是 PawBench 或 OpenTelemetry 规定的格式。

## 实践任务

创建 `fixtures/traces/retry_manifest.json`，为 `retry.json` 的模拟运行手写一个 JSON 对象，包含：

| 字段 | 类型 | 要求 |
|---|---|---|
| trace_id | string | 与 retry.json 的 trace_id 相同 |
| simulated | boolean | 固定为 true |
| model | object | 包含字符串 name、version |
| harness | object | 包含字符串 name、version |
| tools | array | 至少包含一个对象，每个对象有字符串 name、version；本例包含 SQL 工具 |
| data_snapshot | string | 模拟数据快照标识 |

本次运行是合成样例。模型、Harness、工具版本和快照标识请使用你自己编写、含 `mock` 的模拟值，不要冒充已实际运行的模型或版本。

## 验收标准

1. 文件是合法 JSON 对象，六个字段及子字段齐全、类型正确，名称和版本非空。
2. trace_id 与 retry.json 的所有 Span 一致；模拟标记为 true。
3. 清单能分别识别模型、Harness、SQL 工具与数据快照，并明确使用模拟值。
4. 能用一句话解释为什么模型版本和 Harness 版本需要分开记录。

## 面试考点与踩坑

- 同一模型搭配不同 Harness，工具路由和执行方式可能不同；分开记录才有条件设计对照。
- 只记录版本不等于已经完成归因或保证完全复现，还需要控制环境、输入和采样等因素。
- 未知真实版本应明确标记未知，不应编造；本题的 mock 值仅表示合成练习。

## 提交与评审记录

- 2026-11-01 首次评审：JSON 语法正确，Trace ID 与三条 Span 一致，simulated 为 true，包含 SQL 工具。
- 需修改：顶层目前是数组，题目要求单个对象；model 和 harness 缺少 version；模拟模型、Harness、工具版本及数据快照需用含 mock 的值明确区分真实配置。
- 等待补充一句话说明为什么模型版本与 Harness 版本分开记录。
- 未代改学员清单；等待修订并复评。
- 2026-11-01 应学员要求，教师改为顶层对象，补充模型和 Harness 的版本，并明确各模拟值。已验证字段、类型、SQL 工具及与三条 Span 的 Trace ID 一致。
- 文件验收条件已满足；学员关于模型与 Harness 版本为何分开记录的一句话说明尚未提交，因此课时尚未标记为通过。修改由教师完成，不能作为学员独立实现的证据。
- 学员回答“模型版本和harness不一样”，认识到两项配置不同，但尚未说明控制变量或归因；教师补充同一模型比较不同 Harness 时应固定模型等其他条件，等待学员进一步回答。
- 学员在提示后正确回答：比较两个 Harness 时保持模型版本相同。结合已验证的清单，本课通过；清单修改由教师协助完成。
