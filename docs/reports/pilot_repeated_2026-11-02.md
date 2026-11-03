# 试点重复评测报告（2026-11-02）

## 实验范围与冻结证据

本次用同一 DeepSeek 模型和同一 Harness，对 Golden、Regression **分别**运行：每集合 2 道已仲裁合成题，每题重复 2 次。运行前固定 Task SHA-256、评测器源码 SHA-256、Harness 源码摘要和重复次数。私有总清单：`runs/pilot_repeated/aeb433fd29f64b2f8dfe0164a800ca27/plan.json`；各 Trial、Trace 和完整评分在清单引用的 `runs/batches/` 与 `runs/trials/` 下。Holdout 未参与。

| 集合 | Task 数 | Trial 数 | 规则总体通过 | 顺序轨迹通过 | 已观测平均 token | 安全结论 |
|---|---:|---:|---:|---:|---:|---|
| Golden | 2 | 4 | 4/4 | 4/4 | 607.25（4/4 有观测） | unknown |
| Regression | 2 | 4 | 3/4 | 3/4 | 620.33（3/4 有观测） | unknown |

顺序轨迹专项审计保存在同目录的 `trajectory_audit.json`。Golden 与 Regression 是**不同题目集合**，不能把两行差值解释为版本提升或退化。每集合仅两题，Task Bootstrap 区间分别为 `[1.0, 1.0]` 和 `[0.5, 1.0]`；第一项的零宽度只说明两道题的重复观测都成功，**不表示总体成功率已精确到 100%**。所有安全状态未知，不应解释为安全通过。

## 失败样本归因

Regression 的 G 题第 2 次 Trial：首个规划 Span 选择正确 SQL 工具，工具 Span 成功返回；随后模型规划 Span 返回自然语言而非约定 JSON，解析器抛 `ValueError`，根 Span 终止为 error。该 Trial 的 Trace 有效地记录了失败链，但 Trial 状态为 error、最终答案缺失，因此规则和轨迹均判失败。批次层面的 `error_type=ExceptionGroup` 是 MCP 会话异常包装；根因应结合模型 Span 的 `ValueError` 和冻结原始模型输出判断。不能因为前 1 次 G Trial 成功而丢弃这次失败。

这是 **模型输出契约失败** 的单次可观测证据；可能受提示词、模型随机性或接口适配共同影响，不能仅凭一例断言模型总体能力差。后续应在相同 Task 上增加重复次数，并在固定模型时单独比较提示词/Harness 版本，避免同时改变多个因素。该离线失败已在 Regression 中，不应冒充线上 Badcase。

## 当前限制与下一步

四题共享一份订单 CSV，且只覆盖单一净收入题型，不能代表工业级业务分布。Holdout 仅两题，已封存但本轮未开封；不依据本轮结果对 Holdout 调参。下一步扩大 Golden/Regression 的业务变化和负样例，增加人工抽样与 Judge 校准，再冻结候选版本和验收门槛后决定是否开封 Holdout。
