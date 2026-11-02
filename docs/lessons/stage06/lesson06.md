# 6.6 现成评测工具或 Benchmark 实践

状态：小规模 Inspect AI 框架实践已通过（教师实现，2026-11-02）；非公开 Benchmark 成绩。

[阶段文档](README.md) · [总计划](../../plan.md)

## 课时定位

选择一个现成评测工具或公开 Benchmark，完成一次小规模运行与结果分析。解释任务格式、输入输出、评分逻辑、失败原因与复现条件，并对照自建流水线理解其差异。6.5 的真实人工校准仍待补；本课的框架实践不替代该验收。

开课时根据项目适配性与官方文档确定工具、版本和范围，只选一个方向。区分自建任务接入框架与公开基准复现，保留运行范围与配置，不把小样本试运行称为完整基准成绩。

## 方法论与框架映射

本课选用 UK AI Security Institute 的 **Inspect AI 0.3.287**。官方 Task 由 Dataset、Solver、Scorer 构成；Sample 有 `input`、`target`、`id`、`metadata`，自定义 Scorer 从 `TaskState` 与 `Target` 返回 `Score`。[官方教程](https://inspect.aisi.org.uk/tutorial.html) · [官方 Scorer 文档](https://inspect.aisi.org.uk/custom-scorers.html)

本项目的映射是：两道冻结订单题 → Inspect Dataset；已有 LangGraph＋MCP Agent → 自定义 Solver；金额与 SQL Trace 核验 → 自定义 Scorer。Inspect 自带评测日志和准确率聚合；项目自建流水线仍负责正式四集合隔离、双标仲裁、Trial 环境重置、轨迹校验和安全门禁。两套结果不能未经核对直接合并。

## 实践输入、输出与运行记录

教师实现 [Inspect 接入练习](../../../src/merchant_agent/evaluation/inspect_practice.py)。输入为冻结的 `orders.csv` 与 A/B 门店请求；Solver 每题建立新 SQLite，调用现有 LangGraph/MCP。为验证框架接线，基座使用规则测试模型，Inspect 命令中的 `mockllm/model` 仅满足框架模型配置，**实际回答由 Solver 内的规则测试模型产生**。Scorer 要求唯一“分”金额、目标门店的成功 SQL Span 和一致 Trace；输出 `C/I`、答案与失败解释。

复验命令：`PYTHONPATH=src INSPECT_TRACE_FILE=runs/inspect_logs/trace.log UV_CACHE_DIR=/private/tmp/agent-eval-inspect-cache uv run --no-project --with inspect-ai --with mcp --with langgraph --with requests inspect eval src/merchant_agent/evaluation/inspect_practice.py --model mockllm/model --log-dir runs/inspect_logs --limit 2`。Inspect 单独安装在临时环境，未修改项目依赖。

复验日志：[Inspect 原生评测日志](../../../runs/inspect_logs/2026-11-02T11-20-11-00-00_merchant-store-net-practice_DKFvYbmxN6BVYTBdg9BMKC.eval)。读取日志确认状态 `success`，两条样本 `inspect_store_a`、`inspect_store_b` 的分数均为 `C`，框架显示 accuracy 1.000。相应答案是 12000 分和 8000 分。日志位于 Git 忽略的 `runs/`，仓库克隆者不会自动拥有该证据文件。

## 验收与局限

已完成小规模运行、解释 Task/Solver/Scorer 输入输出、读取样本级分数并与自建流水线对照。**这不是公开 Benchmark 复现，也不是 DeepSeek 能力测量**；规则测试模型知道如何选工具，只证明外部框架能承载现有 Agent。Inspect 的模型 token 统计不代表 Solver 内测试模型的调用量。真实模型评测需另接模型端口、固定版本和配置，并使用正式标注样本。

## 面试考点与踩坑

问：Inspect 的 `target` 与项目 Oracle 有何关系？答：本练习由冻结 CSV 计算目标金额；正式任务必须遵循双标与入库门禁。问：为什么不能引用 accuracy 1.000 作模型成绩？答：Solver 内是规则测试模型，两题样本只验证适配器。问：第三方日志与自建 Trace 怎样关联？答：本练习通过 Sample ID、Inspect 日志和 `runs/inspect_practice/` Trace 对应；生产需显式 Trial ID 与哈希映射。问：为什么 Scorer 同时查 Trace？答：避免仅凭答案字符串把无工具证据的样本判对。

## 提交与评审记录

2026-11-02：教师阅读 Inspect 官方文档，在临时环境安装 0.3.287，完成两题小规模实际运行并读取 Inspect 原生日志；结果 2/2，仅作为框架接入证据。项目全套 pytest 199 passed。
