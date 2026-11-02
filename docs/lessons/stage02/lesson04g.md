# 2.4g 搜索证据快照

状态：已通过。

[2.4 总览](lesson04.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15—20 分钟。

## 知识点

网页搜索结果会随时间变化。评测若只记录最终答案，难以复查 Agent 当时看到了什么。搜索结果应保存当次的标题、URL、摘要和获取时间；这只是检索快照，不证明网页正文支持答案。后续 Trace 课会把快照关联到工具调用 Span。

## 实践任务

新建 `src/merchant_agent/tools/search/search_snapshot.py`，实现：

```python
def make_search_snapshot(query: str, results: list[SearchResult]) -> dict:
    ...
```

返回可 JSON 序列化的字典，固定结构：`{"query": query, "results": [每条 SearchResult 的字典]}`。使用 `dataclasses.asdict` 转换每条结果；不访问网络，不修改输入对象，也不在此函数补造时间字段。

## 验收标准

1. 两条结果保留原顺序和全部五个字段；空列表得到 `"results": []`。
2. `json.dumps` 可序列化；修改返回字典不改变原始 `SearchResult`。
3. 输出标记为检索快照，不能声称已经核验网页正文。

## 面试考点与踩坑

- 搜索结果快照能帮助复现“Agent 当时看到了什么”。
- URL 和摘要是来源线索，内容可能过期或被注入指令。
- 后续要记录查询、工具版本和请求错误，才能做完整轨迹归因。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：检查时 `search_snapshot.py` 仍为空文件，未发现可验收实现；状态保持进行中。
- 2026-11-01：学员保存实现后复评；两条结果的顺序与字段、空结果、JSON 序列化和输入对象不被修改均通过。本课完成。
