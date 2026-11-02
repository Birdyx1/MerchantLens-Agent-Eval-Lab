# 2.4e 解析真实搜索服务的响应

状态：已通过。

[2.4 总览](lesson04.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20 分钟。

## 知识点

接入真实服务前，先把第三方返回的数据转换为项目自己的 `SearchResult`。这样 Agent 不必直接依赖服务商的字段名。Tavily 的搜索结果位于 `results`，包含 `title`、`url` 和 `content`。[Tavily 官方文档](https://docs.tavily.com/documentation/api-reference/endpoint/search)

这节只解析模拟响应，不发起网络请求，也不需要 API Key。下面的严格校验是项目约定，不代表 Tavily 所有响应都必须包含这些字段。

## 实践任务

新建 `src/merchant_agent/tools/search/tavily_parser.py`，实现：

```python
def parse_tavily_results(payload: dict, retrieved_at: str) -> list[SearchResult]:
    ...
```

约定输入 `payload` 为已解析的字典，`retrieved_at` 由调用方提供 UTC 时间文本。本课不校验时间格式。

1. 要求 `payload["results"]` 存在且是列表；缺失或类型不对，抛 `ValueError`。空列表返回 `[]`。
2. 每一项必须是字典，`title` 和 `url` 必须是非空字符串；`content` 缺失时使用空字符串，存在时必须是字符串。无效项抛 `ValueError`。
3. 按原顺序生成 `SearchResult`：`content` 映射到 `snippet`，`provider` 固定为 `"tavily"`，`retrieved_at` 使用传入值。

## 验收标准

- 两条模拟结果能正确映射，缺失 `content` 时摘要为空。
- 空结果返回 `[]`；缺失结构、错误类型和无效结果项抛 `ValueError`。
- 不发送网络请求；不把解析失败当成无搜索结果。

## 面试考点与踩坑

- 为什么做字段映射？隔离服务商格式变化，让 Agent 使用稳定的数据契约。
- 为什么解析失败不返回空列表？否则评测无法区分“没有结果”和“工具出错”。
- `retrieved_at` 是检索时间，并不表示网页的发布时间或事实正确性。

## 提交与评审记录

- 2026-11-01：应学员要求先接真实 API；本课调整为后续解析课。
- 2026-11-01：学员选择 Tavily，课时改为解析 Tavily 响应。
- 2026-11-01：2.4d 真实请求通过，开始本课，等待学员提交。
- 2026-11-01：学员实现解析函数；两条结果、缺失 content、空结果与错误结构均通过模拟测试。本课通过。
