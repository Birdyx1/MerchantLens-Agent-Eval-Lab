# 3.1 基座模型适配

状态：已通过（教师收尾实现）。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

基座模型适配层只定义 Harness 可依赖的调用接口与返回数据，不直接绑定 OpenAI 或本地模型 SDK。后续 LangGraph 节点依赖这个接口，模型更换时无需改图结构。这是项目架构约定，不是 LangGraph 的固定类型。

LangGraph 的图由 **State、Node、Edge** 组成：State 保存节点之间共享的数据，Node 执行一次步骤并返回状态更新，Edge 决定下一步。图需要 `compile()` 后才能运行。模型适配器是 Node 调用的依赖，不是图本身。[官方 Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) · [官方设计指南](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)

## 实践任务

`src/merchant_agent/agent/model_port.py` 定义不可变 `ModelResponse` 与 `ModelPort` 协议。学员手写初稿；按最新要求由教师补齐中文文档字符串与协议方法体，并用可替换模型做接口测试。此课不调用真实模型，也不建 LangGraph 图。

## 验收标准

1. `ModelResponse` 包含 `text: str`、`model_id: str`、`input_tokens: int`、`output_tokens: int`。
2. `ModelPort` 暴露 `async generate(messages: list[dict[str, str]]) -> ModelResponse`。
3. 不导入具体模型 SDK；模块可独立导入。

## 面试考点与踩坑

模型能力与 Harness 编排要能独立替换和比较；调用接口返回 token 用量，后续成本评测才能计量。协议负责约束调用形状，运行时仍需验证真实提供商返回的数据。

## 提交与评审记录

- 2026-11-01：开课；按学员要求提供完整参考代码，由学员手写后提交评审。尚未验收。
- 2026-11-01：首次评审：`ModelResponse` 字段与 `ModelPort.generate` 签名符合任务，但 `generate` 缺少方法体；`py_compile` 报 `IndentationError`。需在方法内缩进写 `...`，再复评。
- 2026-11-01：学员补入空文档字符串后模块可导入；随后学员要求改回教师实现、自己理解架构。教师将协议方法体明确写为 `...`，补中文说明与测试。固定模型可替换调用、响应不可变性通过；全套 pytest 47 passed，本课通过。
