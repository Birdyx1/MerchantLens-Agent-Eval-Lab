# 7.1 基座能力准入

状态：基座准入小样本已通过（教师实现，2026-11-02）；规模化准入阈值与多次运行待补。

[阶段文档](README.md) · [总计划](../../plan.md)

## 方法论：先测基座，再谈 Harness 归因

基座准入直接调用 `ModelPort.generate`，不进入 LangGraph、MCP、工具执行或重试。这样可观察模型对工具选择格式、指令跟随和代码表达式的原始能力；若此层失败，不能先归咎于 Harness。反之，基座通过也不保证 Agent 端到端成功。字节 Data Agent 的分层评测与阿里 PawBench 的 Model × Harness 对照都强调这一拆分；三道探针及判定规则属于本项目工程选择。

本课三道探针：① 指定 JSON 契约选择 `get_store_net(store_id=A)`；② 严格输出 `{"status":"ready"}`；③ 输出净收入 Python 表达式，并用多组输入验证。代码表达式通过 AST 白名单解释，不执行模型生成的任意代码。每题只调用一次，失败和原始输出留在记录中，不能反复重试到通过后只报最好结果。

## 实践与真实证据

教师实现 [基座探针与确定性评分](/Users/xueganping/StudyProject/agent-eval/src/merchant_agent/evaluation/base_admission.py)和 [DeepSeek 运行入口](/Users/xueganping/StudyProject/agent-eval/src/merchant_agent/evaluation/base_admission_live.py)。真实运行使用已配置的 `deepseek-flash`，结果存于 Git 忽略的 `runs/base_admission/`，权限 `600`，不写入 API Key。

首轮真实运行 2/3：工具路由输出 `{"tool":"get_store_net","arguments":{"store":"A"}}`，不符合 Harness JSON 契约。但首轮题面未明确给出该契约，是**探针设计缺陷**，不能把它直接记作模型能力失败。修正题面后重新运行，三题均通过；[修正后运行记录](/Users/xueganping/StudyProject/agent-eval/runs/base_admission/05b7509f0d394ef18b0f166c4e4d8ef5.json)保存原始输出和用量。该结果只说明三道小探针在一次运行中通过，尚不能证明模型稳定达到生产准入阈值。

## 验收标准与面试考点

验收：三类输出都由代码判定；恶意代码表达式不执行；模型调用失败计失败并保留原因；真实运行保留版本、输出与 token 用量。专项 pytest 3 个，完整测试结果见提交记录。

面试问：为何要直接调模型？答：隔离 Harness 和工具影响。为何首轮 2/3 不直接归因于模型？答：题面与评分契约不一致，测量工具本身有偏。为什么代码探针用多组向量？答：避免模型写死单个样例答案。为什么 3/3 不等于能力准入完成？答：样本量和重复次数太小，尚缺置信区间与跨任务覆盖。

## 提交与评审记录

2026-11-02：教师实现三类直接模型探针；修正工具路由题面后真实 DeepSeek 一次运行 3/3。首轮不公平探针结果保留用于评测设计复盘。全套 pytest 202 passed。
