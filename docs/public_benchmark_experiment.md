# BFCL / BIRD 公开基准子集实验

本实验增加公开开发基准的外部验证，不替代商家经营分析领域评测，也不修改项目 Holdout。

## 预先固定的实验设计

- 清单：`fixtures/public_benchmarks/pilot_v1.json`，40 道公开题目，抽样种子 `20261103`，模型运行前冻结。
- BFCL v4：`simple_python / multiple / parallel / irrelevance` 四类别，每类随机 5 题。DeepSeek 与 GLM 分别每题 3 次，共 120 Trial。
- BIRD Mini-Dev：使用 Hugging Face 2026 更新的固定提交，5 个数据库各 4 题。按难度分组打乱后按 simple / moderate / challenging 轮转抽取；同一 DeepSeek 模型对比 direct / react，每题每配置 3 次，共 120 Trial。
- 数据库为 california_schools、student_club、thrombosis_prediction、toxicology、superhero。为了控制下载及本地执行资源选择这五个较小数据库，明确存在数据库选择偏差。
- 总计 240 Trial，按固定种子打乱调度，并发 4。失败和超时保留，无自动重试；不看模型结果后换题、换提示或提高预算。

## 输入与评分

- BFCL 仅向模型提供公开工具文档和问题。两个模型使用统一 JSON 调用数组协议，不调用官方模型 handler，不是原生 function calling 测试。
- 使用 BFCL 固定版本 `ast_checker.py` 的原始函数体，仅隔离无关 SDK 与 Java/JavaScript 导入，并为此 JSON 协议配置“不转换函数名”。irrelevance 以空调用数组判定。
- BIRD 两配置都获得同一问题、公开 evidence 和完整 SQLite 表/视图 DDL。参考 SQL 不进入模型上下文。
- direct 生成一次 SQL；react 最多 5 次模型调用，可查询数据库、观察响应并修正，最后提交 SQL。ReAct 是实验专用的受限 SQL 循环，不冒充项目完整 LangGraph Agent 的官方基准成绩。
- BIRD 使用固定官方 `calculate_ex` 函数：预测和参考结果行的集合完全相等；不增加项目自有浮点容差，不进行 SQL 文本匹配。
- 查询通过 SQLite `mode=ro`、`query_only` 和授权器执行；拒绝写入、DDL、ATTACH、PRAGMA 和扩展文件访问。单 SQL 执行限制 10 秒、完整结果上限 50,000 行，超过上限记失败，不截断后评分。
- 工具观察最多展示前 20 行，并说明实际行数和是否截断；最终 EX 使用完整结果。最终评分查询不计入 Agent 的工具调用次数。

## 运行预算与度量

- `temperature=0`；API 超时 90 秒；每次最大输出 2,048 Token。
- ReAct 累计输入输出预算 24,000 Token，在每次响应后检查；最多 5 次模型调用；每轮开始检查 Trial 180 秒预算。同步 API 的超时为单次请求上限，整条 Trial 的墙钟耗时可能超过 180 秒。
- GLM 显式禁用 thinking；DeepSeek 沿用 Responses 接口默认值。记录真实返回的模型标识，两个提供方的服务栈和解码细节不能视为完全相同。
- 分别报告总体成功率、每题 3 次全部成功的经验比例、至少成功一次的比例、失败分型、难度/类别结果、平均/P95 耗时、模型调用和工具调用次数。
- Token 均值只用用量可观测的完整响应 Trial，并报告观测数量；API 错误的缺失用量不当成零成本。不同模型的 Token 数也不能直接等同于货币费用。
- 差值按题目配对、按题目 Bootstrap 2,000 次；不把同题重复当成不同任务，不宣称总体或生产显著提升。

## 命令

首次冻结（已有清单时拒绝覆盖）：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.public_benchmark_cli prepare
```

新环境恢复清单中指定的官方数据及评分源码，然后校验全部哈希和参考 SQL：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.public_benchmark_cli restore
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.public_benchmark_cli verify
```

执行新批次（读取本地已有的 DeepSeek / SiliconFlow 配置，产生 API 调用费用）：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.public_benchmark_cli run
```

离线从记录重建报告，不调用模型：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.public_benchmark_cli report --run-dir runs/public_benchmarks/<run_id>
.venv/bin/python -m pytest tests/test_public_benchmark.py tests/test_siliconflow_chat_model.py -q
```

离线核验 240 个计划 Trial 是否齐全、汇总与原始文件是否一致、输入是否与冻结题目相同，并重算确定性评分：

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.benchmark_audit --run-dir runs/public_benchmarks/<run_id>
```

此操作验证记录和评分可复算，不保证重新调用非确定性模型会产生逐字相同的输出。

原始题目、数据库和逐次模型输出位于 Git 忽略的 `runs/public_benchmarks/`；固定清单、来源 URL、哈希、实验代码和汇总报告可版本管理。不要将本实验输出转成所谓真人标注。

## 官方来源及许可

- [BFCL 官方代码与数据](https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard)，来源提交与文件哈希见冻结清单。项目根目录 Apache-2.0 许可随来源下载保留。
- [BIRD Mini-Dev 官方数据](https://huggingface.co/datasets/birdsql/bird_mini_dev/tree/5b256b5a9c17478f06ed6912612e9a14d17065c8)，[官方评测脚本](https://github.com/bird-bench/mini_dev/blob/1c49a375e76c471e218564da3f4617513d33e371/evaluation/evaluation_ex.py)。Mini-Dev README 标注 CC BY-SA 4.0；清单所含题目按此来源归属，不声称原创。
- SQLite 文件来自官方压缩包，下载时锁定 ETag 并对抽取文件记录 SHA256；只用 HTTP Range 下载所需数据库。

公开基准、模型服务和题目会更新，复现时固定提交及哈希；跨版本分数不能直接比较。清单包含参考答案，只能由评测侧读取，模型上下文构造器只选取 input 字段。
