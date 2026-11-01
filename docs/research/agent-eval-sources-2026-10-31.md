# Agent 评测资料索引：大厂技术实践与面经

检索日期：2026-10-31（Asia/Shanghai）。配套阅读：[必背知识与方法论](agent-eval-interview-guide.md)。

面试练习版：[50道知识点面试题与答案](agent-eval-interview-qa.md)。

## 使用口径

- 本轮筛选 28 项资料：14 项厂商文章或官方文档、8 项原始论文/开源项目/标准文档、6 项面经线索。
- A 类用于理解厂商公开实践；B 类用于核对概念与评测方法；C 类只说明公开帖子中出现了哪些问题，不代表公司统一题库。
- “官方产品文档”“公司技术团队博客”“开发者账号文章”“用户面经”分别标记，不把社区域名自动等同于公司背书。
- 日期只填写页面明确披露的日期；没有完整年份的不推断年份。访问状态是本次检索结果，动态文档后续可能变化。
- 配套指南的优先级是备考建议，没有做面试题频率统计，也没有取得企业内部资料。

## A. 厂商技术文章与官方文档

| ID | 来源与标题 | 类型/日期 | 本次可见性 | 阅读目标 |
|---|---|---|---|---|
| A01 | 美团：[Agent评测漫谈——由浅入深讲解Agent评测](https://tech.meituan.com/2026/08/07/Agent-Evaluation.html) | 技术团队博客；2026-08-07 | 已打开正文 | 理解结果、过程、效率、风险，以及长程任务评测 |
| A02 | 美团：[《Agent评测白皮书》系列01：Agent评测全览](https://tech.meituan.com/2026/09/10/Agent-Evaluation-White-Paper-01.html) | 技术团队博客；2026-09-10 | 已打开正文 | 理解评测资产、Rubric、评测体系与Agent自身两条迭代闭环 |
| A03 | 阿里云开发者：[自动化评测的九九归一——评测agent](https://developer.aliyun.com/article/1710689) | 开发者账号文章；2026-02-05；文末注明来源“阿里云开发者公众号”、作者翠翰 | 已打开正文及署名 | 评测Agent、领域知识增强、人工复审；其业务效果为作者报告，未独立复现 |
| A04 | AgentScope：[Evaluation](https://doc.agentscope.io/tutorial/task_eval.html) | 官方项目文档；动态页 | 已打开正文 | Task、SolutionOutput、Metric与批量评测；具体功能以对应版本为准 |
| A05 | 魔搭EvalScope：[Agent评测](https://evalscope.readthedocs.io/zh-cn/latest/user_guides/agent/index.html) | 官方项目文档；动态页 | 已打开正文 | 内置AgentLoop与外部Agent Bridge，模型工具能力与成品Agent的评测边界 |
| A06 | 阿里云Hologres：[Agent评估](https://help.aliyun.com/zh/hologres/user-guide/agent-evaluation-in-holoscope) | 官方产品文档；动态页 | 已打开正文 | 幻觉、忠实度、相关性等评估器；内置阈值属于产品口径 |
| A07 | 火山引擎：[从扣子，看AI Agent产品开发范式演进](https://developer.volcengine.com/articles/7509048150372712467) | 厂商开发者社区文章；正文以2025年为背景 | 已打开正文 | 开发、评测、观测、优化，以及Trace回流 |
| A08 | 扣子：[扣子罗盘，让Agent开发调优不再迷航](https://www.coze.cn/loop) | 官方产品介绍；动态页 | 搜索内容可见；直接打开无可读正文 | 认识观测、评测、Prompt调试的产品分工；产品介绍不能代替技术验收 |
| A09 | 火山引擎日志服务：[AgentLoop平台概述](https://docs.volcengine.com/docs/torch-log-service/agent-loop-overview?lang=zh) | 官方产品文档；动态页 | 已打开正文 | 运行观测、问题沉淀、离线实验及版本比较 |
| A10 | 腾讯云：[智能体开发平台·应用评测](https://cloud.tencent.cn/document/product/1759/104208) | 官方产品文档；动态页 | 已打开正文 | 基准评测、模型/Prompt配置对比，以及规则、代码、模型裁判 |
| A11 | 腾讯朱雀实验室：[谁是Agent最强守门员？SkillTrustBench正式发布](https://matrix.tencent.com/zh/2026/06/17/first-skill-trust-bench) | 官方实验室研究文章；2026-06-17 | 已打开正文 | 区分Skill可信度和扫描器效果；安全评估同时看漏报与误报 |
| A12 | 腾讯：[TSecBench自主Agent评测与验证基础设施](https://tsecbench.zc.tencent.com/) | 官方域名评测平台；动态页 | 搜索抓取内容可见，含数据加载失败提示；直接打开超时 | 受控环境、统一预算、成功率/耗时/Token；这是安全任务平台，不能外推为通用能力排名 |
| A13 | 微软：[Agent Framework Evaluation](https://learn.microsoft.com/en-us/agent-framework/agents/evaluation) | 官方开发文档；动态页 | 已检索并打开 | 将任务、工具、质量、安全拆为不同评估维度 |
| A14 | Anthropic：[Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) | 官方工程/研究文章；2026-01-09 | 已打开正文 | Task/Trial/Grader、裁判类型、能力/回归评测、pass@k与pass^k |

阿里、腾讯、字节的条目同时包含技术文章和产品文档，二者用途不同。A03虽由开发者账号发布且标明公众号来源，页面仍带社区贡献免责声明，不将其业务数字视为独立验证结论。没有用其他个人投稿补齐所谓“官方最佳实践”。

## B. 必须知道的原始项目与研究

| ID | 原始来源 | 应该掌握 | 使用边界 |
|---|---|---|---|
| B01 | Berkeley：[BFCL V3：Multi-Turn & Multi-Step Function Calling](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html) | 工具选择、参数、多轮、多步骤；执行后状态验证 | V3方法文档，发布2024-09-19、更新2024-12-10；不是声称V3为当前最新版 |
| B02 | Sierra：[τ-bench原始仓库](https://github.com/sierra-research/tau-bench) | 用户模拟、业务规则、工具交互与重复试验可靠性 | 原仓库已提示后续系列；比较成绩必须注明代际、数据及配置 |
| B03 | SWE-bench：[官网与评测入口](https://www.swebench.com/) | 真实仓库issue修复、执行测试与回归保护 | 注明具体子集、环境、Agent脚手架与运行预算 |
| B04 | WebArena：[原始项目仓库](https://github.com/web-arena-x/webarena) | 可执行Web环境、任务与业务状态验收 | DOM/截图动作成功不等于业务完成 |
| B05 | THUDM：[AgentBench](https://github.com/THUDM/AgentBench) | 多类交互环境中的Agent能力评测 | 是公开基准之一，不是所有业务Agent的统一验收标准 |
| B06 | Ragas：[Available Metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/) | 检索、回答忠实度、工具调用、目标完成等指标分工 | 指标输入与实现依版本变化；部分指标本身依赖LLM |
| B07 | OpenTelemetry：[Traces](https://opentelemetry.io/docs/concepts/signals/traces/) | Trace、Span、父子关系、时间、属性与上下文传播 | 自定义JSON存储不自动等同于OTLP格式；Agent字段不都属于稳定统一标准 |
| B08 | 原始论文：[Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685) | 位置、冗长、自我偏好等Judge偏差 | 研究结论不是某个新模型在所有业务上的固定偏差数值 |

## C. 面经：把原题、二次整理与备考推导分开

| ID | 平台/标题 | 页面披露时间 | 本轮核验状态 | 可确认的相关考点 |
|---|---|---|---|---|
| C01 | 牛客：[字节跳动9.3 Agent开发一面面经](https://ac.nowcoder.com/discuss/1672892) | 编辑于09-04；题目指9.3，未据此补年份 | 已读原帖题目正文；自述面经，身份未独立核验 | Harness；5分钟任务变15–20分钟如何分析；工具入参可靠性；压缩的信息损失；结构化评分 |
| C02 | 牛客：[美团AI-Agent开发一面，面了70分钟，全程都在问我怎么证明它行](https://www.nowcoder.com/feed/main/detail/a826dc9c857e4351bde7dc1d43840072) | 文中面试10.15，页面编辑10-22；年份未独立确认 | 已读原帖题目正文；作者复盘观点不等于公司要求 | 工具描述导致选错工具如何改；多工具顺序；全自动可靠性；哪部分真正影响指标 |
| C03 | 牛客：[AI应用研发二面面经分享-阿里云](https://www.nowcoder.com/feed/main/detail/b0a0fc09ba0b408c9df84d38c6d1eb83) | 可见正文未给明确面试日期 | 已读原帖题目正文 | Agent死循环；Prompt幻觉约束；切分策略；向量检索准确性如何校验 |
| C04 | 牛客：[滴滴-测开-代驾事业部一面](https://www.nowcoder.com/feed/main/detail/d8186eefae3e4a6da31a6bcc24500c35) | 搜索页显示相对日期，不转换成绝对日期 | 原帖检索题目内容可见；直接打开失败 | Agent项目指标从哪里来、评测怎么做；人工介入规范；RAG与知识库更新 |
| C05 | 牛客：[6.16字节测开大模型面经3面](https://www.nowcoder.com/feed/main/detail/5d31bf4d22b841ac99bde746ef3b5e6f) | 标题6.16，年份未确认 | 搜索摘要明确可见；直接打开未取得正文，仅站点导航 | 仅确认摘要出现“针对coze的skill功能设计评测集”，不补写其他题目 |
| C06 | 测试人社区：[字节国际化测开一面：Skill怎么评估、Web UI Agent哪里容易失控？](https://ceshiren.com/t/topic/36247) | 页面发布2026-10-12；整理中标注面试2026-06-24 | 已读正文；明确属于面经整理汇编 | Skill使用前后评估、Web UI Agent链路、RAG检索；参考答案是整理者补充，不能当原面试官答案 |

C01–C04属于原帖自述材料；C05只作有限线索；C06属于二次整理。因此不将六项都称为“已核验的一手面经”，不宣称某题“每场必问”。

## 推荐阅读顺序

1. A01 → A02：先建立中文整体框架。
2. A14 → B02：理解试验、裁判和可靠性指标。
3. A04/A05、A09/A10：理解系统如何落地。
4. B01、B06、B07、B08：补齐工具、RAG、Trace、Judge知识。
5. A11：补安全与Skill供应链评测。
6. C01–C06：用真实公开问题检验自己是否能讲出证据和实验设计。

不是所有来源都需要通读。面试准备优先看方法、指标定义、失败归因及可复现条件，暂不背动态榜单名次与产品版本数字。
