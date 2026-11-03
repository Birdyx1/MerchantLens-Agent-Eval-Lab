# 阶段 6：硅基流动三模型面板接入与首题验证（2026-11-03）

## 配置与协议

三个裁判模型配置为 `zai-org/GLM-5.3-Flash`、`tencent/Hy4-preview`、`Qwen/Qwen3.8-27B`。它们属于不同模型家族，但共用硅基流动供应商和 API，平台故障、路由或服务层偏差仍可能相关。密钥只保存在本地被 Git 忽略的 `.env`，报告和运行记录不保存密钥。

根据[硅基流动官方 Chat Completions 接口](https://docs.siliconflow.cn/docs/api/chat-completions-post)，新增[适配器](../../src/merchant_agent/agent/siliconflow_chat_model.py)，将 `messages`、`choices[0].message.content` 和 `usage.prompt_tokens/completion_tokens` 映射到项目 `ModelPort`。现有 DeepSeek Responses 适配器不适用于这一响应格式。

## 首题结果

在[已由两位真人独立盲审的虚构挑战](judge_challenge_calibration_2026-11-03.md)上运行[三模型面板入口](../../src/merchant_agent/evaluation/live_siliconflow_panel_challenges.py)。先用第一题验证三个模型；任一票缺失即停，不继续六题。私有原始记录：`runs/siliconflow_panels/76b9981b24d241aea5efeccf495a6cc9/results.json`。

| 模型 | 首题状态 | 分数或错误 |
| --- | --- | --- |
| `zai-org/GLM-5.3-Flash` | 有效 JSON 评分 | 1 分；人工参考分 0 |
| `tencent/Hy4-preview` | 连接失败 | `ProxyError` |
| `Qwen/Qwen3.8-27B` | 连接失败 | `ConnectionError` |

Hy4 和 Qwen 各进行一次额外的无业务数据最小连通性重试，仍分别得到 `ProxyError`、`ConnectionError`。因此当前**没有形成三模型面板结论**；这两个错误不能证明模型 ID 无效，也不能说明模型评分质量。完整六题未启动。

GLM 对“查询已完成，请查看结果”给 1 分，理由是把“查询已完成”视为“有完成查询的结论”；两位人工标注者均给 0 分，因为没有可理解的**净收入**结论。这是实际 Rubric 解释分歧，应进入裁判校准清单。原 `judge_clarity_v1` 和人工标签保持冻结；若要澄清“结论”的含义，应制定新 Rubric 版本并重新盲标、重跑，不能回写旧版本。

## 待完成

1. 核实硅基流动端点与网络代理连接；分别确认 Hy4、Qwen 的模型可用性和 JSON 响应契约。
2. 三模型首题全部有效后再运行剩余五题，记录逐票分歧、模型 ID、成本与人工复核结论。
3. 在自然 Agent Trial 中复现 0/1 分边界；受控挑战不能代表业务分布。

后续已完成[六题三模型试点](siliconflow_heterogeneous_panel_full_2026-11-03.md)：连接恢复后形成 5 题多数结论，其中 1 题多数票错误；另 1 题因 Qwen 评分契约错误而不完整。本报告保留为首次失败尝试的独立审计证据。
