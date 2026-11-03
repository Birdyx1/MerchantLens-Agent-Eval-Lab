# 阶段 4：封存 Holdout 首次真实运行（2026-11-03）

## 目的与边界

阶段 4 缺口记录为「2 道独立数据题已封存，未运行模型」。本次对封存 Holdout 做**首次且预期一次性**的真实运行，补上该缺口。运行后该 Holdout 即被使用，**不再视为未见数据**，后续不得据其调参。

## 样本

`holdout/tasks/` 中两道已仲裁题，共享独立快照 `holdout/fixtures/reserved_orders.csv`：

| Task | 门店 | 题型 | Oracle（分） |
| --- | --- | --- | ---: |
| reserved_store_net_h_001 | H | store_net | 31250 |
| reserved_store_net_j_001 | J | store_net | 22000 |

封存时记录 `model_runs_at_seal: 0`，本次之前确未运行模型。

## 方法与可追溯性

- 教师代写入口：`src/merchant_agent/evaluation/live_holdout_pilot.py`。
- 直接复用 `run_trial`，由 `prepare_eval_dispatch` 以 `split=holdout` 识别，不绕过集合隔离；运行前冻结题面 SHA-256。
- 真实运行 deepseek-flash 的 LangGraph + MCP SQL，再跑 Code Judge（3 条 store_net 判据）与 LLM 清晰度裁判。
- 私有机器可读记录：`runs/holdout_runs/96c5b25dc62842fdaaff5ef794cc4b98/results.json`。

## 结果：2/2 全部通过（阴性）

| Task | Trial | Code 三判据 | Judge | 最终回答 |
| --- | --- | :---: | :---: | --- |
| h_001 | completed（split=holdout） | 3/3 | 2 | 门店 H 的净收入为 31250 分（即 312.50 元）。 |
| j_001 | completed（split=holdout） | 3/3 | 2 | 门店 J 的净收入为 22000 分（即 220.00 元）。 |

## 结论与局限

1. 补齐了「封存 Holdout 从未运行」的形式缺口，并留下可追溯证据。
2. 但结果为 2/2 全对，与[边界难例探测](failure_probe_2026-11-03.md)的 4/4 全对一致，进一步印证：**`store_net` 题型对 deepseek-flash 已饱和**，扩大数据难度或更换独立快照都不足以诱发失败。
3. 这是**一次性观测**，样本仅 2 条、单一题型；既不能据此声称模型稳定能力，也不能声称评测体系有判别力。Judge 的 0/1 分覆盖依然缺失。
4. 该 Holdout 已被使用，后续版本对比不应再以其冒充独立数据。

## 下一步

两个阴性结果共同指向同一根因：任务契约只支持 `store_net` 单工具单次调用。要补齐失败样本与跨题型归因，需要**扩展任务契约**（新增题型与判据分组），这是下一阶段的架构级工作。
