# 阶段 6/7：跨题型多步任务失败探针（2026-11-03）

## 目的与背景

[边界难例探测](failure_probe_2026-11-03.md)（4/4 全对）与 [Holdout 首次运行](holdout_pilot_2026-11-03.md)（2/2 全对）共同证明：`store_net` 单步题型对 deepseek-flash 已饱和，扩大数据难度补不出失败样本。本次做**跨题型重构**，新增 `store_net_sum`（两门店净收入合计，多步任务），验证多步任务能否诱发自然失败。

## 契约扩展（教师代写，保持 store_net 向后兼容）

- `schemas/eval_task.schema.json`：`task_type` 扩展为 `store_net | store_net_sum`，`oracle` 按题型用 `if/then` 约束；`store_net` 结构完全不变。
- `schemas/rubric.schema.json`：`check_key` 增加 3 个合计题判据。
- `src/merchant_agent/evaluation/task.py`：`EvalTask` 增加 `expected_total_fen`、`required_tool_calls`，`store_net` 字段保持原样。
- `src/merchant_agent/evaluation/rubric.py`：`CHECK_CONTRACTS` 按 `task_type` 分组。
- `src/merchant_agent/evaluation/code_evaluator.py`：按题型分支；合计题优先取“合计/总计/共计”附近金额。
- `src/merchant_agent/evaluation/trajectory_evaluator.py`：按题型分支，合计题检查两次工具调用各自有匹配规划。
- 新增 `rubrics/store_net_sum_v1.json`。
- 测试：原 261 条全部通过，新增 6 条合计题测试，合计 **267 passed**。

## 样本设计（合成探测，draft，不入正式集合）

| Task | 门店 | Oracle 合计（分） |
| --- | --- | ---: |
| trap_store_net_sum_ab_001 | A + B | 20000 |
| trap_store_net_sum_vw_001 | V + W | 1,244,443 |

题面：「请查询门店 A 和门店 B 的净收入合计，单位为分。」（V/W 同理）

## 结果：2 题中 1 题真实失败、1 题评分器假阴性

私有记录：`runs/failure_probe/262decac10bb4dfd95fedda1ec857906/results.json`；同轨迹重评：同目录 `rescore.json`。

### ab 题：真实失败（参数提取错误）

模型实际调用了：

```
get_store_net(store_id="门店A")  → empty_result
get_store_net(store_id="门店B")  → empty_result
```

数据库里的门店 ID 是 `"A"`/`"B"`，模型把用户请求中的**「门店A」整串当作 store_id**，两次都查空，于是如实回答“数据不可用、无法计算合计”。Code 三判据全部失败，LLM 清晰度裁判给 **1 分**（明确但缺金额）。

这是一个**自然产生的模型失败**，不是故障注入，也不是脏输入对抗；它第一次让 Judge 打出 1 分（此前全部 2 分），补上了「Judge 从未有 0/1 分压力」缺口的一半。

### vw 题：评分器假阴性（已修复）

模型正确调用 `get_store_net("V")=1234567`、`get_store_net("W")=9876`，并正确回答「合计 1,244,443 分（门店 V：1,234,567 分；门店 W：9,876 分）」。

但原评分器 `_answer_amount` 只接受“恰好一个金额”，而该答案含**三个**金额（合计 + 两个分项），于是 `answer_amount_fen=None`，判失败。这与 G 题千位分隔符是同类**评分器假阴性**。

修正：新增 `TOTAL_PATTERN`，合计题优先取「合计/总计/共计」附近的分金额；无合计表述时才退回“唯一金额”。**不重新运行模型**，对原 Trial 同轨迹重评：

| Task | 原评分 | 重评 |
| --- | --- | --- |
| ab | 失败 | 失败（真失败） |
| vw | 失败（假阴性） | **通过**（合计 1,244,443） |

## 对照实验：表述对参数提取的影响

为验证 ab 题失败是否可复现，新增 4 道对照题（同一契约、修复后评分器）：

| Task | 题面 | 工具实际 store_id | 结果 |
| --- | --- | --- | --- |
| ab_id | 「门店 ID 为 A 和门店 ID 为 B」 | A / B | 通过 |
| de | 「门店 D 和门店 E」 | D / E | 通过 |
| de_id | 「门店 ID 为 D 和门店 ID 为 E」 | D / E | 通过 |
| xy | 「门店 X 和门店 Y」（含零净收入） | X / Y | 通过 |

对照显示：**ab 题的失败是偶发的模型参数提取错误，不是稳定复现**。同为「门店 X 和门店 Y」的普通表述，de、vw、xy 三题都正确提取了纯 ID，只有 ab 一次把「门店A」整串传参；明确写「门店 ID 为 X」的 ab_id 也正确。私有记录：`runs/failure_probe/d33196175de64477aef3b05163bf6b98/results.json`。

## 结论与局限

1. **多步任务能诱发自然失败，但失败是偶发的**：ab 题是第一个真实失败样本；6 道合计题中仅 1 次失败，说明失败来自模型输出随机性（同为「门店 X 和门店 Y」的 3 次普通表述中 1 次出错），不能据此推断稳定失败率。这反而印证了重复试验（5.4）的必要性。
2. **失败样本量仍极小**：只有 1 条真失败，不能推断失败率或认为模型“整体多步能力弱”。
3. **评分器必须随题型扩展**：vw 题说明新题型会暴露旧评分器的假阴性；本次已修复并同轨迹重评，但合计题只有 2 条样本，正则覆盖仍需更多边界样本验证。
4. 两题均为教师新增合成探测题，`draft`、未双标共识，**不入 Golden/Regression/Holdout**，不得计入正式成功率或标注一致性。

## 下一步

1. 扩大多步任务样本（不同门店组合、含退款/大额），观察参数提取错误的复现率与分布。
2. 把「合计识别」的正则边界纳入回归测试（已完成 2 条，可继续补畸形分组、负值、多合计）。
3. 用这批自然失败样本做 Judge 校准（0/1/2 分覆盖），补齐阶段 6.5 的真实失败校准。
