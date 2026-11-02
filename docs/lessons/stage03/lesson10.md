# 3.10 真实模型适配器

状态：已通过（教师实现，2026-11-02）；DeepSeek 真实网络调用已验收。

[阶段文档](README.md) · [总计划](../../plan.md)

## 知识点

`ModelPort` 让 Harness 不依赖供应商 SDK。本课用 `requests` 调用 OpenAI Responses API，并把返回文本、实际模型 ID、输入和输出 token 转为 `ModelResponse`。模型选择值与实际返回的模型版本不能混为一谈。接口字段依据[官方 Responses API 文档](https://developers.openai.com/api/reference/typescript/resources/responses/methods/create)。

## 实践任务

实现 `OpenAIResponsesModel`：配置模型、密钥、HTTPS 接口及请求超时；将消息转换为 API 输入；校验完成状态、文本和用量。工具观察以带来源标记的用户文本传入，不伪造 API 的工具调用 ID。

## 验收标准

- 替身 HTTP 响应可验证请求形状和返回转换；异常结构被拒绝。
- 使用实际响应的模型 ID；不把密钥写入 Trace 或异常正文。
- 全套 pytest 通过。真实联网调用单独验收，当前不计入通过证据。

## 面试考点与踩坑

`asyncio.to_thread` 让同步 `requests` 不阻塞事件循环，但取消协程不会强制终止已启动的 HTTP 线程；请求自身超时仍必需。工具观察当作不可信输入，后续需补更强的提示注入防护。切换本地模型服务时另写适配器，保持同一个 `ModelPort`。

## 提交与评审记录

2026-11-02：教师实现；新增 5 个替身 HTTP 测试，全套 pytest 112 passed。

2026-11-02：最初把 DeepSeek 密钥用于 OpenAI 接口，服务端返回 HTTP 401。识别服务商后增加 `DeepSeekResponsesModel`，固定官方 `/responses` 接口，并把本地配置迁移为 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL=deepseek-flash`。真实最小请求成功，返回 `deepseek-flash`，输入 58 token、输出 86 token，规划 JSON 有效。未记录或输出密钥。

[DeepSeek 官方 Responses API 指南](https://api-docs.deepseek.com/guides/responses_api/)说明了接口兼容性和服务地址；[官方接入文档](https://api-docs.deepseek.com/quick_start/agent_integrations/)列出当前模型名。
