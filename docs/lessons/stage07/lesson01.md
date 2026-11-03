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

2026-11-03：[双模型直接探针](../../reports/base_admission_comparison_2026-11-03.md)使用相同三题各运行一次，DeepSeek 和 GLM 均 3/3。工具题直接给出目标工具和参数，主要测格式遵循，不能证明自主工具选择；规模化与无答案泄露探针待补。

2026-11-03：新增[多工具选择探针](../../reports/base_tool_selection_2026-11-03.md)，只给工具定义及题面，不提供期望动作；DeepSeek 严格通过 4/4，GLM 2/4，另两题因 Markdown 代码块违反严格 JSON 契约。工具和参数在解析失败时记为未知，人工可读正确不等于契约通过。

2026-11-03：补齐[八道多工具选择评测集](../../reports/multi_tool_selection_2026-11-03.md)，覆盖选错工具、参数缺失和多工具混淆；每题预写期望工具与参数，题面不泄露动作。DeepSeek 与 GLM 各 8 题×2 次，固定接口与解码参数。原始严格 AST 评分下两模型各 14/16；发现 `python_text` 的变量赋值/f-string 写法被误判后，用安全 AST 子集解释器对同一批输出重评，不重跑模型，重评后均 16/16。GLM 在显式“不要 Markdown”指令下 0/16 代码块，移除该句后 2/16，剥离代码块后工具与参数均正确，说明是提示词敏感的格式层问题。样本仍小，未观察到选错工具或参数错误，不能据此推断稳定能力。
