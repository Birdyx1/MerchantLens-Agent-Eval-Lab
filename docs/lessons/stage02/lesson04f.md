# 2.4f 接入搜索服务接口

状态：已通过。

[2.4 总览](lesson04.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15 分钟。

## 知识点

前面分别完成了请求、解析和统一接口。本课把它们接起来，Agent 只调用 `search(query, limit)`，无需知道服务商的原始响应格式。`retrieved_at` 应记录实际获取时间，使用带 UTC 时区的时间文本。

## 实践任务

新建 `src/merchant_agent/tools/search/tavily_provider.py`，定义 `TavilySearchProvider`，提供：

```python
def search(self, query: str, limit: int) -> list[SearchResult]:
    ...
```

依次调用 `request_tavily_payload(query, limit)`、生成当前 UTC 时间、调用 `parse_tavily_results(payload, retrieved_at)`，并返回结果。可以用 `datetime.now(timezone.utc).isoformat()`。保持现有错误向上传递，不把请求失败转成空列表。

## 验收标准

1. mock 请求与解析函数，验证参数、调用顺序和返回值。
2. 结果的 `retrieved_at` 是带 UTC 时区的时间文本。
3. 请求失败或解析失败时异常向上传递，不返回 `[]`。
4. 完成 mock 验收后，再用已配置的 Key 做一次真实查询；只展示数量和字段是否存在，不输出正文或 Key。

## 面试考点与踩坑

- 适配层把外部服务的字段和异常隔离在工具层，方便替换提供商。
- 空结果与请求失败要区分，否则 Agent 和评测器会误判。
- `retrieved_at` 是获取时间，不等于网页发布时间。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：学员实现适配类；mock 验证参数、UTC 时间、请求和解析错误传播。真实 Tavily 端到端查询返回 1 条结果，字段与 provider 标记完整；未输出正文或 Key。本课通过。
