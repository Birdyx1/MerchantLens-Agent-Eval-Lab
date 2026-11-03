# 9.1 异常识别

状态：进行中（代码与真实扫描完成，阶段复盘待补）；教师实现，2026-11-03。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

异常识别是从 Trial/Trace 中筛出「值得标注与入库」的候选，而不是直接判定业务对错。本课识别 5 类确定性异常：

- `trial_not_completed`：Trial 状态非 completed（error/timeout/incomplete）；
- `budget_exhausted`：终止原因是 `max_steps` / `max_tokens`；
- `tool_failure`：工具 outcome 属于失败类（invalid_input/timeout/program_error 等）；
- `security_rejected`：出现越权拒绝（critical）；
- `ungrounded_answer`：回答含金额，但没有任何成功的工具调用支撑。

## 实践任务

实现 `anomaly.py`（`collect_anomalies` + `summarize`）与真实扫描入口 `live_anomaly_scan.py`，扫描 `runs/trials/` 下的全部 Trial。

## 验收标准

- 7 条单元测试覆盖 5 类异常与汇总；
- 真实扫描可运行并输出按类型/严重度的汇总。

## 真实扫描结果（2026-11-03）

扫描 147 个 Trial，24 个存在异常，共 25 条：

| 类型 | 数量 |
| --- | --- |
| trial_not_completed | 13 |
| tool_failure | 12 |

全部为 high 严重度。异常明细包含 trial/task 定位，供后续脱敏、标注与入库。

## 面试考点与踩坑

- 问：异常识别与评测评分是什么关系？答：评分判「任务是否通过」，异常识别判「证据是否值得回流」；两者互补，不能互相替代。
- 坑：把 `tool_failure` 直接当模型失败——它可能是环境故障（SSLError 等），需与 `trial_not_completed` 一起看。
- 坑：`ungrounded_answer` 只是启发式（有金额无成功工具），不能单独断言幻觉。

## 提交与评审记录

2026-11-03：教师实现 `anomaly.py`、7 条测试与真实扫描；147 Trial 中识别 24 个异常 Trial。未评审。
