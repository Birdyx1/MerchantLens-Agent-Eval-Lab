# 业务覆盖与负样例扩充草稿

状态：L/M/P/Q 四题在 2026-11-03 完成双标一致、共识、冻结数据复算与受控入库（L/M Golden，P/Q Regression），扩充后的[重复评测报告](reports/expanded_2026-11-03.md)已生成。N 仍是公开校准例；负样例候选未正式入库。

## 业务边界

新增订单快照 `fixtures/business_data/coverage_orders.csv` 和 `fixtures/business_data/coverage_extra_orders.csv`，五道草稿在 `fixtures/eval_task_coverage/`。L 覆盖无退款，M 与 Q 覆盖不同退款组合，P 覆盖较大金额和多笔订单。N 的零值结果曾在本文件中提前披露，**只能作为公开校准例，不能再计入独立盲标或标注一致性统计**。其余四题仍属于单一 `store_net` 题型，只扩充金额和退款边界，不代表多业务场景。每题已有待复核的代码参考值，但标注者应只用 `annotation_cli show` 和 CSV 独立计算，不打开含 Oracle 的 Task 草稿。

入集计划在标注前冻结：L（无退款）与 M（混合退款）进入 Golden，用于扩大正常业务口径的版本横比；P（较大金额、可能触发千位格式）与 Q（不同环境快照和退款组合）进入 Regression，用于防止金额解析和环境切换时退化。N 保留为公开校准例，不进入正式集合。四题已通过双人独立标注、共识、Oracle 复算和集合隔离门禁；同一题未跨集合重复。若要做可靠的版本对比，需继续扩大不同用户表达、退款组合和环境快照，并保持集合任务清单冻结。

## 对抗候选

`fixtures/negative_input_candidates.json` 含 4 条歧义/脏输入候选：缺失门店、指代不明、空白 ID 和含 SQL 指令片段的 ID。当前只是项目自定义 `NegativeInputCase` 契约，尚不能通过正式 `EvalTask` Schema 或 Negative Set 入库器，也未经过语义 Rubric、双标与安全门禁。硬约束可查不应发生的工具调用；“澄清/拒绝是否恰当”仍需人工与 Judge 校准。不得把这四条算作已完成的安全评测。

下一步扩展正式负样例 Task/Trial 契约，明确安全 Oracle 与评测侧隔离，之后才能入 Negative Set 和运行。当前 4 条负样例仍只是未仲裁候选。

## 快速标注入口

本地[批量盲标向导](../src/merchant_agent/evaluation/annotation_batch_cli.py)一次接收多道 Task，逐题只显示题面和订单文件，要求本人输入可解性、金额、门店与证据说明；已提交的题自动跳过。它不展示 Oracle、机器参考解或其他人的标签，也不自动计算金额。两位真人应分别运行，各自使用不同 `reviewer_id`，不能把同一人的两次输入当成独立标注。批量入口只减少终端操作，不改变双标、仲裁和入库门禁。
