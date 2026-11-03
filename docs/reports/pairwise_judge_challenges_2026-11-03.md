# 阶段 6.2：真实双顺序成对比较试点（2026-11-03）

## 设计

从已由两位真人独立盲审的[虚构清晰度挑战](judge_challenge_calibration_2026-11-03.md)中取三对同题替代回答，覆盖人工参考分 0 对 1、1 对 2、0 对 2。两条回答在比较函数中绑定相同示例 Task ID 与 Task 摘要，但它们是**人工构造的替代回答，不是真实 Agent Trial**；不进入正式四集合。

每对用硅基流动 `zai-org/GLM-5.3-Flash` 在 A/B 与 B/A 两种顺序各评一次。裁判只收到固定 Rubric 和两条回答，不收到设计分数或人工标签。顺序归一后若两次选同一回答，才记稳定胜者；不一致则记 `unstable`。代码见[成对裁判](../../src/merchant_agent/evaluation/pairwise_judge.py)及[真实运行入口](../../src/merchant_agent/evaluation/live_pairwise_challenges.py)。

第一次试跑的首个输出不是严格 JSON，运行器拒绝评分，私有失败记录为 `runs/pairwise_challenges/2f4c47d779854341863354923c4260f6/results.json`。根据[硅基流动官方 JSON 模式说明](https://docs.siliconflow.cn/docs/userguide/guides/json-mode)，后续固定 `response_format={"type":"json_object"}`，仍由代码验证字段与值，未放宽解析规则。

## 结果

私有成功记录：`runs/pairwise_challenges/313283fca1b246569d56338a7f2f3148/results.json`。

| 比较 | 人工参考层 | A/B 选择 | B/A 选择 | 归一结果 |
| --- | --- | --- | --- | --- |
| `no_conclusion` vs `missing_unit` | 0 vs 1 | 右 | 左 | 第二条胜，稳定 |
| `missing_unit` vs `clear_fen` | 1 vs 2 | 右 | 左 | 第二条胜，稳定 |
| `contradictory_amounts` vs `clear_conversion` | 0 vs 2 | 右 | 左 | 第二条胜，稳定 |

三对共六次有效调用，均与人工参考分的相对顺序一致，且换位后稳定。Judge token 合计 **2,833**。这些成对结果只说明本次三对没有观察到位置翻转；不能宣称模型无位置偏差，更不能把相对偏好当成业务正确率。实际两个答案可能都错误，或两者差异过小而不稳定；需要更多同题真实 Trial 与人工抽样复核。
