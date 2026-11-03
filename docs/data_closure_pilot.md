# 评测数据闭环：第一批盲标试点

状态：4 道合成业务题均已双标一致、形成共识并通过冻结 CSV 复算；D/F 入 Golden，E/G 入 Regression。四题各有一次真实 DeepSeek Trial；G 题暴露评分器千位分隔符缺陷，已保留原评分并基于同一 Trial 重评。全套 pytest 221 passed。日期：2026-11-02。

## 目标与边界

先用同一份冻结订单快照制作 4 道“门店净收入”题，完成：两名真人独立标注 → 一致性比较 → 分歧仲裁 → Oracle 修正 → 受控入库 → 真实 Agent Trial → Trace、评分与报告。四题只够验证流程，不能据此估计稳定能力或 κ。它们的来源是 `synthetic`，不能写成线上回流。

数据位于 `fixtures/business_data/pilot_orders.csv`，Task 草稿位于 `fixtures/eval_task_pilot/`，对应门店 D、E、F、G。**草稿 JSON 含待复核 Oracle，标注者不要打开。** 标注者只运行 `annotation_cli show` 查看盲标包，再直接读取 CSV 计算；不要看 Rubric 示例、已有标注或本人的同伴答案。净收入口径为该门店每行 `paid_fen - refunded_fen` 后求和，单位为分。

## 当前第一步：两人独立标注

在项目根目录执行（示例只显示 D 题；其余把 `d` 改成 `e/f/g`）：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.annotation_cli show fixtures/eval_task_pilot/pilot_store_net_d_001.json
```

标注者自行计算后提交；以下 `AMOUNT` 要替换成本人算出的整数，不要在公开聊天中发出答案：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.annotation_cli submit fixtures/eval_task_pilot/pilot_store_net_d_001.json --reviewer-id reviewer_one --amount-fen AMOUNT --store-id D --evidence-note '本人独立核对订单行并按 paid_fen-refunded_fen 求和'
```

第二位真人使用自己的 ID（例如 `reviewer_two`），不读取第一人的结果、Task 草稿 JSON 或本聊天里的计算结果。`reviewer_id` 只是区分文件，不是身份认证；协作时需真实保证两人独立。记录保存在 Git 忽略的 `runs/annotations/`，提交后不可覆盖。

## 后续验收门槛

1. 四题均有两份真人记录，且 Task/环境哈希一致。
2. 逐字段报告可解性、金额和门店 ID 一致率；任何分歧需第三人写仲裁理由。
3. 独立复算冻结 CSV，最终 Oracle 与仲裁一致，再将 Task 改为 `adjudicated`。
4. 通过 `EvalSetStore.register` 入 Golden 或 Regression；另备独立、未参与开发调参的数据作为 Holdout。四题太少，正式比例与统计结论待扩样。
5. 同题重复真实 DeepSeek Trial，保留模型/Harness/工具版本、完整 Trace、规则评分和失败归因。之后再做 Judge 人工校准与四格实验。

## D 题闭环记录

- 第一轮 Trial 在模型连接阶段失败，Trace 根节点记录 `ConnectionError`；保留为环境故障，不计为模型能力失败。私有记录：`runs/data_closure/0515cfc94dd94554b785f4f2f638fef6.json`。
- 第二轮在允许外网的环境运行，Trial 状态 completed，Trace 校验通过，三条 Code Rubric 判据及顺序轨迹判据通过；1 次 SQL 工具调用、总计 600 token。安全状态为 unknown，不等于安全通过。私有记录：`runs/data_closure/16596e35aea64ba5bb99d6b1b1fa05cf.json`。
- 两份记录的 reviewer ID 不同，但本地 ID 不构成真实身份或独立性的技术证明；“两位真人独立”依赖参与者的实际操作承诺。只凭一道 D 题不能报告稳定成功率、标注一致性总体指标或 Judge 校准结果。

## E 题与跨题一致性

- E 题两份标注一致，共识记录通过冻结数据复算，已通过入库门禁进入 Regression。
- E 题真实 DeepSeek Trial completed，Trace、三项 Code Rubric 和顺序轨迹判据通过；1 次 SQL 工具调用、总计 672 token，安全状态 unknown。私有记录：`runs/data_closure/8d8c8d54e79a455baae5d627302a0747.json`。
- D/E 两题精确一致率与各字段一致率均为 1.0；可解性 κ 为 `null`，因为两题都在同一可解类别，随机一致率为 1。报告及源记录哈希保存在 `runs/data_closure/agreement_de.json`。两题样本量极小，不能推断总体标注稳定性。

## F 题与三题一致性

- F 题两份标注一致，共识与冻结数据复算通过，已入 Golden。
- F 题真实 DeepSeek Trial completed，Trace、三项 Code Rubric 与顺序轨迹判据通过；1 次 SQL 工具调用、总计 607 token，安全状态 unknown。私有记录：`runs/data_closure/0d32152eea8a413e8704eb0be87483e9.json`。
- D/E/F 三题精确一致率 1.0；κ 仍为 `null`，因为三题均为可解。私有报告：`runs/data_closure/agreement_def.json`。样本与类别分布仍不足以证明标注稳定性。

## G 题：评分器故障与同轨迹重评

- G 题两份标注一致，共识与冻结数据复算通过，已入 Regression。真实 Trial completed，Trace 有效，正确 SQL 工具调用一次。
- 原评分器只匹配不带逗号的金额；模型用规范千位分隔符输出，造成“结果错误、轨迹错误”的假阴性。原始评分保留在 `runs/data_closure/3a62971ee128484eaea2419fc48877df.json`。
- 修正确定性金额解析器并新增规范/畸形分组回归测试。对原始 Trial 与 Trace **不重新运行模型**，用新版评分器重评，规则和轨迹判据均通过。重评文件 `runs/data_closure/g_rescore_001.json` 记录原评分、Trial、Trace 与评分器源码摘要，便于审计评分版本差异。
- D/E/F/G 四题逐字段与整题一致率均为 1.0；可解性 κ 仍为 `null`，因为四题均属“可解”。报告见 `runs/data_closure/agreement_defg.json`。

这四题共用已在开发试跑中使用的 CSV，均不是严格 Holdout；真正的 Holdout 应使用新环境快照并限制开发侧接触。四题只验证了闭环能跑通，正式评测仍需扩充不同业务条件、难例和真实回流，不得用 4/4 声称模型稳定通过率。
