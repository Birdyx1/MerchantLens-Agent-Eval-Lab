# 阶段 6/7：边界难例失败探针（2026-11-03）

## 目的与背景

阶段 6 的人工校准报告已指出：现有真实 Trial「全部是清晰成功答案，没有 0/1 分、含糊表达或金额矛盾的判别压力」。阶段 6.1/6.4/6.5 与阶段 7 均缺「自然失败样本」。本次探针的目标是：**给裁判制造第一次判别压力**，观察评测体系在边界/失败样本上能否区分 0/1/2 分。

本次只验证「边界数据能否诱发自然失败」，不做能力结论。

## 样本设计（教师新增，合成探测，不入正式集合）

新增独立快照 `fixtures/business_data/trap_orders.csv`，四道 `label_status=draft` 的合成探测题位于 `fixtures/eval_task_trap/`，全部属于既有 `store_net` 契约，Oracle 明确可解：

| 题 | 门店 | 设计意图 | Oracle（分） |
| --- | --- | --- | ---: |
| trap_store_net_v_001 | V | 大金额 + 千位格式 | 1,234,567 |
| trap_store_net_w_001 | W | 4 笔订单含一笔全额退款，多退款聚合 | 9,876 |
| trap_store_net_x_001 | X | 净收入接近零 | 100 |
| trap_store_net_y_001 | Y | 净收入恰为零 | 0 |

四题共享同一冻结快照，题面统一为「请查询门店 X 的净收入，单位为分」，变量只有数据难度。

## 方法与可追溯性

- 教师代写探针入口：`src/merchant_agent/evaluation/live_failure_probe.py`。
- 运行前冻结题面 SHA-256、评分器与裁判源码摘要；每题真实运行 deepseek-flash 的 LangGraph + MCP SQL，再跑 Code Judge（3 条 store_net 判据）与 LLM 清晰度裁判。
- 为让 draft 探针题可运行，`run_trial` 新增**可选** `dispatch` 参数：默认仍走 `prepare_eval_dispatch`（集合隔离不变，现有测试 261 passed），探针显式传入 `traffic_type=evaluation_probe / split=probe`。
- 私有机器可读记录：`runs/failure_probe/76ced7e3d03440468899d95fb0e546fa/results.json`。
- Harness 指纹 `source-sha256:4be17500…`；模型 `deepseek-flash`。

## 结果：4/4 全部通过（阴性）

| 题 | Trial 状态 | Code 三判据 | Judge 分 | 最终回答 |
| --- | --- | --- | :---: | --- |
| v（大金额） | completed | 3/3 | 2 | 门店 V 的净收入为 1,234,567 分。 |
| w（多退款） | completed | 3/3 | 2 | 门店 W 的净收入为 9876 分。 |
| x（接近零） | completed | 3/3 | 2 | 门店 X 的净收入为 100 分（即 1.00 元）。 |
| y（零） | completed | 3/3 | 2 | 门店 Y 的净收入为 0 分（即 0.00 元）。 |

四题 Trace 均有效，SQL 调用一次且门店正确，最终回答与工具返回金额一致。

## 结论与局限

1. **`store_net` 题型对 deepseek-flash 已饱和**：加大金额、增加退款、压到零净收入，均未诱发自然失败。这解释了此前 4/4、8/8、16/16、32/32 全对的根因——不是裁判太松，而是题型太简单。
2. **这个阴性结果不能反过来证明「模型能力强」或「裁判区分度好」**：样本仍然全部成功，Judge 的 0/1 分判别力**依旧未被检验**。它只证明「仅靠边界数据不足以补齐失败样本」。
3. 四题是教师新增的合成探测题，**未经双人独立标注与共识**，`draft` 状态，不入 Golden/Regression/Holdout；不得计入标注一致性或正式成功率。

## 下一步

要真正补齐自然失败样本，必须**跨题型**：现有 `eval_task` 的 `task_type` 硬编码为 `store_net`、`get_store_net` 单工具单次调用，无法表达多步推理（如两门店对比）、其他业务指标（退款率、订单数）或多工具任务（搜索、Python）。下一切口是**扩展任务契约支持第二种题型**，使评测集覆盖不同业务场景与失败模式。
