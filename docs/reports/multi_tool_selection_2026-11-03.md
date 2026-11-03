# 阶段 7.1 扩展：多工具选择评测集

日期：2026-11-03。状态：8 道合成题已冻结，DeepSeek 与 GLM 各重复 2 次真实运行完成；输出契约、工具选择、参数正确性分层统计；GLM Markdown 格式问题用同题、同接口、同解码参数的提示词对照做了诊断。

## 目标与边界

本批题目只评价**规划阶段的工具与参数选择**，不执行 SQL、搜索或 Python 工具。题目全部为人工构造的合成题，用于组件级回归，不进入 Golden/Regression 正式集合，也不代表真实业务分布。

覆盖三类目标场景，并额外保留两道基线题：

| 场景 | 题数 | 设计意图 |
| --- | ---: | --- |
| `baseline` | 2 | 直接的门店查询与 Python 字符串任务，建立基线 |
| `wrong_tool` | 2 | 题面含网页/同名门店等干扰词，但正确动作是 `get_store_net` |
| `missing_parameter` | 2 | 必须提取 `limit` 或 `timeout_seconds`，漏参数即参数错误 |
| `tool_confusion` | 2 | 题面含“门店净收入”或“Python”等跨工具关键词，正确动作分别是 `search_web` |

## 冻结题集与防泄露

题集：[`fixtures/multi_tool_selection_v1.json`](../../fixtures/multi_tool_selection_v1.json)，sha256 `1719a694a18c7fb974fa3302616a90b4c2a2c89aa6d1f50b7d14c79c7d69dc97`。

每题在冻结文件中预写期望工具和参数；运行入口 `build_messages` 只发送公开工具定义与题面，期望字段不会进入模型上下文。`tests/test_multi_tool_selection.py` 校验：

- 题面不包含期望工具名或 `expected` 字段；
- 用户消息只等于题面原文；
- 题集至少 6 题、ID 唯一、期望参数符合公开工具契约。

单题判据摘要如下，便于从运行记录反查冻结题面：

| 题目 | 场景 | 期望工具 | 判据 sha256 前缀 |
| --- | --- | --- | --- |
| `store_direct` | baseline | `get_store_net` | `0acd4b9b4f84580f` |
| `store_mentions_web` | wrong_tool | `get_store_net` | `994e5f395f62a4e9` |
| `web_mentions_store` | tool_confusion | `search_web` | `9dbdea5497f8d255` |
| `web_english_limit` | missing_parameter | `search_web` | `13c2266be113c40b` |
| `python_arithmetic` | missing_parameter | `execute_python` | `cfc55de1afaf433d` |
| `python_text` | baseline | `execute_python` | `ad9d5bc5392fe063` |
| `store_noisy_web_hint` | wrong_tool | `get_store_net` | `5050ed877f32c71d` |
| `web_python_keyword` | tool_confusion | `search_web` | `3f6995a2bbad8fb8` |

## 固定模型、接口与解码参数

主运行每题重复 2 次，共 16 次/模型：

| 模型 | 接口 | 模型版本 | temperature | top_p | timeout | JSON mode |
| --- | --- | --- | ---: | ---: | ---: | --- |
| DeepSeek | Responses | `deepseek-flash` | 0.0 | 未发送 | 60s | 关闭 |
| GLM | Chat Completions | `zai-org/GLM-5.3-Flash` | 0.0 | 1.0 | 90s | 关闭 |

模型请求失败也会写入记录；本批 32 次调用无网络或接口错误。主运行输入摘要：`8f11a1cfc6f733970a8ec80979be44c26a822f34b411585a53f68b700b6be5da`；公开指令摘要：`b03eba8d26f784bf365e3b99b4f43c4293fbcbc0b855629d7626d441bfeb47e1`。

私有记录：`runs/multi_tool_selection/e7fe1b89ca084b0a8857f94fb1ea82c4/results_rescored.json`。原始评分记录 `results.json` 保留，未覆盖。当前评分器 sha256 `2f454304db3be117cb9fa111f80d5ba2a517240fc173efb343de63317fdca266`；原始严格 AST 评分器 sha256 `852c79ea05fe2e071d7a9284cdffee1e13b8f7b5d347acdaeed84ee441cc45a8`。

## 分层统计口径

三条统计彼此独立，避免把解析失败算成模型选错：

- **输出契约**：严格 JSON，且顶层为 `plan`/`action`，`action` 为 `type` 固定为 `tool` 的结构；Markdown 代码块、额外文字、结构缺失均为格式失败。
- **工具选择**：仅在契约通过后比较工具名；解析失败时工具记为“未知”，不进入工具正确率分母。
- **参数正确性**：仅在工具选择正确后比较参数；工具错误或解析失败时参数记为“未知”，不进入参数正确率分母。
- **失败类型**：`call_error`（调用失败）、`format`（契约/格式失败）、`wrong_tool`（工具错误）、`parameter`（参数错误）、`passed`。

## 主运行结果

先说明一次评分器修正：原始评分器对 `execute_python` 使用严格 AST 相等，把两模型语义正确但带变量赋值或 f-string 的代码判成参数错误。修正后先用 AST，再用安全子集解释器比较 `.count` 字面量和打印整数；**没有重新调用模型**，只对同一批冻结输出重评。原始评分保留。

| 阶段 | 模型 | 输出契约 | 工具选择 | 参数正确 | 整题通过 | 未知工具/参数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 原始严格 AST | DeepSeek | 16/16 | 16/16 | 14/16 | 14/16 | 0 / 0 |
| 原始严格 AST | GLM | 16/16 | 16/16 | 14/16 | 14/16 | 0 / 0 |
| 重评后 | DeepSeek | 16/16 | 16/16 | 16/16 | 16/16 | 0 / 0 |
| 重评后 | GLM | 16/16 | 16/16 | 16/16 | 16/16 | 0 / 0 |

原始 4 次参数错误全部来自 `python_text`：两模型都写成 `s = 'agent-eval'` 后再 `print(s.count('-'))` 或先赋值 `count`，另有 GLM 使用 f-string 输出。它们与冻结判据的差异是写法而非语义；安全解释器只接受白名单语句、字符串 `.count` 和整数运算，不执行任意代码。重评变化 4 条，原始 `score` 保存在每条结果的 `original_score`。

## 失败类型

| 运行 | 模型 | 调用失败 | 格式失败 | 选错工具 | 参数错误 | 通过 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 主运行（重评后） | DeepSeek | 0 | 0 | 0 | 0 | 16 |
| 主运行（重评后） | GLM | 0 | 0 | 0 | 0 | 16 |
| GLM 无显式禁令诊断 | GLM | 0 | 2 | 0 | 0 | 14 |

主运行中 8 道题、两模型、各 2 次均通过，说明本批题面没有诱发可观察的选错工具或参数错误；这是当前的回归基线，不能据此声称模型在更难的业务题上稳定。诊断运行的 2 次失败全部是格式层，工具和参数在剥离代码块后均正确。

## GLM 的 Markdown 格式问题

主运行指令明确写了“不要 Markdown、代码块或额外文字”，GLM 16 次全部是严格 JSON，Markdown 包裹 0 次。

为判断这是否只是提示词压制，另做一次 GLM 诊断：题集、模型、接口、temperature/top_p 和重复次数不变，只移除“不要 Markdown、代码块”这半句，保留“只输出一个 JSON 对象”和“不要输出其他内容”。诊断输入摘要 `5586dddae9680dd15471dc2d1035e762dbb71ba48509490a4298cd53e69664c5`，私有记录 `runs/multi_tool_selection/f286ecffb1ed4e0c9197b54b285bccfb/results_rescored.json`。

| 指令条件 | GLM 调用 | 严格契约 | Markdown 包裹 | 剥离后工具/参数正确 | 严格整题通过 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 显式禁止 Markdown/代码块 | 16 | 16/16 | 0 | — | 16/16 |
| 未显式禁止 | 16 | 14/16 | 2 | 2/2 | 14/16 |

两次 Markdown 分别出现在 `web_python_keyword` 第 1 次和 `python_arithmetic` 第 2 次；内容都是合法 JSON，且工具与参数完全正确。它们按严格契约记为格式失败，工具和参数记为未知，不误记为选错工具或参数错误。

结论：本模型/接口配置下，Markdown 包裹是**提示词敏感的输出格式问题**，不是稳定的工具选择能力缺陷。此前 4 题探针中 GLM 2/4 出现代码块，本次未显式禁止时 2/16，显式禁止时 0/16；方向和量级一致，但题量、题面和历史解码配置不同，不能把差异单独归因于模型能力。若要用 `response_format=json_object` 消除该层差异，应另做接口模式对照并单独报告，不能与文本模式结果混在同一张表。

## 验收对照

| 验收标准 | 证据 |
| --- | --- |
| 至少 6 道合成题，覆盖三类场景 | 8 道题；`baseline` 2、`wrong_tool` 2、`missing_parameter` 2、`tool_confusion` 2 |
| 预写期望工具和参数，且只在评测侧 | 冻结 fixture 的 `expected` 字段；`build_messages` 只发送公开指令和题面；防泄露测试通过 |
| 契约、工具、参数分别统计，解析失败记未知 | 三层评分与 `unknown_tool`/`unknown_arguments`；诊断运行 2 次格式失败的工具/参数均为未知 |
| 固定模型、接口和解码参数，每题至少 2 次 | 配置表；主运行 2 模型 × 8 题 × 2 次；诊断同配置仅改一句提示 |
| 保留所有输出和失败记录 | `results.json` / `results_rescored.json` 保存每次输出、token、错误类型与原评分；本批无调用错误 |
| 分模型、分失败类型报告，分析 GLM Markdown | 主运行与诊断的失败类型表；Markdown 对照小节 |
| 每个样本可追溯到冻结题目与判据 | fixture sha256、每题 `criteria_sha256`、输入/指令/评分器摘要均写入运行记录 |

## 限制

- 8 题均为合成短题，主运行两模型全对，不能估计真实业务分布上的工具选择准确率。
- 每题仅 2 次重复，只能观察一致性，不能给出稳定准确率或置信区间。
- Python 参数的语义检查只覆盖白名单子集；语义等价但写法超出子集的代码仍可能被判错。
- 只覆盖一个供应商的两个模型；模型轴包含适配器与接口差异，不能单独归因于模型能力。
- 未执行真实工具；本报告只评价规划，不覆盖工具执行、Trace 或端到端结果。

## 复现

```bash
# 主运行：DeepSeek + GLM，8 题 × 2 次
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_multi_tool_selection

# 对已有冻结输出重评，不调用模型
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.rescore_multi_tool_selection \
  runs/multi_tool_selection/<run_id>/results.json

# GLM Markdown 诊断：只移除显式代码块禁令
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_multi_tool_selection_markdown
```
