# 2.4d 调用真实网页搜索 API

状态：已通过。

[2.4 总览](lesson04.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：25—35 分钟。

## 知识点

Tavily 网页搜索使用 POST 请求，地址为 `https://api.tavily.com/search`；请求体是 JSON，认证使用 `Authorization: Bearer <API Key>`。[官方 API 文档](https://docs.tavily.com/documentation/api-reference/endpoint/search)

真实请求需要 Tavily API Key。[免费套餐](https://www.tavily.com/pricing)提供每月 1,000 credits，无需信用卡；具体消耗以账户和请求类型为准。Key 通过本地环境变量传入，不提交到仓库，也不要发送给教师。

## 实践任务

分步完成：输入、Key、请求参数、状态码、响应大小及 JSON 解析已通过阶段性检查；当前处理网络异常，随后真实联调。最终验收仍覆盖本节全部要求。

### 当前小步：处理网络异常

在 `requests.post` 和分块读取外围捕获 `requests.exceptions.RequestException`，转为固定消息的 `RuntimeError`，用 `from None` 避免异常链暴露请求信息。不要吞掉现有的 HTTP 状态、大小或 JSON 错误。

验收：mock 模拟连接错误与超时，均转为不含 Key 的 `RuntimeError`；原有错误分类仍正确。测试不发送网络请求。[Requests 官方文档](https://requests.readthedocs.io/en/latest/user/quickstart/)

在 `src/merchant_agent/tools/search/tavily_client.py` 中使用 `requests` 实现：

```python
def request_tavily_payload(query: str, limit: int) -> dict:
    ...
```

- `query` 去首尾空白后必须非空字符串；`limit` 为 1～10 的整数且不是布尔值。非法输入抛 `ValueError`。
- 从环境变量 `TAVILY_API_KEY` 读取 Key；不存在或为空时抛 `RuntimeError`，不发请求。
- 使用 POST 和 JSON 请求体，字段为 `query`、`max_results`、`search_depth`（固定 `"basic"`）、`auto_parameters`（固定 `false`）；设置 Bearer 认证头、5 秒超时和 `allow_redirects=False`。`timeout` 不等于整个调用的总时限。
- 使用流式读取，最多保留 1 MiB 响应；解码 JSON，顶层必须是字典。非 2xx（包括 3xx）、超时、超限、非法 JSON 或错误顶层类型抛 `RuntimeError`。错误消息和日志不要包含 Key、请求头或原始响应体。
- 返回解析后的原始字典；下一课再转成 `SearchResult`。

## 验收标准

1. 用 mock 验证 URL、POST JSON 参数、Key 请求头和超时；不打印 Key。
2. 校验缺少 Key、非法输入、HTTP 错误、超时、超限和非法 JSON；错误不能伪装成空结果。
3. 有可用 Key 时，用一条普通查询做真实联网验证，只报告状态和结果数量；无 Key 时先完成 mock 验收，真实联调明确记录为待完成。

## 面试考点与踩坑

- 真实服务的 Key、限流、超时和错误处理会影响评测结果的稳定性。
- 请求体用 JSON 编码；密钥不能出现在 URL 或日志中。
- HTTP 成功只说明请求成功，搜索摘要仍须验证来源。

## 提交与评审记录

- 2026-11-01：学员选择 Tavily 免费套餐，本课改用 Tavily HTTP 请求；响应映射移至 2.4e。
- 2026-11-01：Key 已在本地环境文件配置；当前先练习函数的输入与 Key 校验，等待学员提交。未进行真实 API 联调。
- 2026-11-01：学员实现输入与 Key 校验，模拟测试覆盖非法查询、无效数量、空 Key 与有效路径，阶段性通过。当前构造 POST 请求对象，尚未发送请求。
- 2026-11-01：POST 请求对象通过模拟 Key 检查，验证请求地址、方法、JSON 字段和请求头；未发送网络请求。下一步实现发送与响应处理。
- 2026-11-01：进入禁止重定向小步，等待学员实现。
- 2026-11-01：学员选择 `requests`；已安装并记录依赖，原 opener 小步取消，当前准备请求参数。
- 2026-11-01：学员使用 `requests.Request(...).prepare()` 构造参数，模拟检查通过；接下来改用 `requests.post` 并检查状态码。
- 2026-11-01：学员完成 `requests.post` 和状态码检查；模拟 200、301、401、500，参数和资源关闭均通过。下一步限制响应大小。
- 2026-11-01：分块读取通过空块、恰好 1 MiB 与超限模拟测试；当前处理 JSON 和顶层类型。
- 2026-11-01：JSON 字典、数组、非法 JSON 和无效 UTF-8 模拟检查通过；当前处理网络异常。
- 2026-11-01：学员完成网络异常转换；连接错误、超时模拟检查通过，异常消息未泄露原始信息。授权环境中使用本地配置的 Key 发起一次真实 Tavily 搜索，请求成功并返回 1 条结果；未输出 Key 或结果正文。本课通过。
