# 2.4b 搜索服务接口

状态：已通过。

[2.4 总览](lesson04.md) · [阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15 分钟。

## 知识点

搜索服务可能更换。先约定统一接口，Agent 调用方只依赖接口；测试时可以提供返回模拟结果的实现。

Python 的 `typing.Protocol` 用于描述对象需要提供的方法；满足方法签名的类可以被类型检查器当作该接口的实现，不需要显式继承。[Python 官方文档](https://docs.python.org/3/library/typing.html#typing.Protocol)

## 实践任务

新建 `src/merchant_agent/tools/search/search_provider.py`，定义继承 `Protocol` 的 `SearchProvider`，包含方法：

```python
def search(self, query: str, limit: int) -> list[SearchResult]:
    ...
```

从上一课的模块导入 `SearchResult`。本课仅定义接口，不调用网络、不实现搜索服务。

## 验收标准

1. 可以从模块导入 `SearchProvider`，其 `search` 方法具有约定的参数和类型标注。
2. 返回类型是 `list[SearchResult]`，不是单条结果。
3. 模拟服务只需提供同名兼容方法，便可作为类型检查意义上的接口实现；本课不要求运行时验证或安装类型检查器。

## 面试考点与踩坑

- 为什么用接口？方便替换服务和注入模拟实现，评测时可减少对外部网络的依赖。
- 类型注解和 Protocol 不会自动验证运行时输入；查询词、数量和错误处理将在实现阶段明确。
- 搜索结果是外部数据，不应把其中的文字当成 Agent 指令。

## 提交与评审记录

- 2026-11-01：开课，等待学员提交。
- 2026-11-01：学员实现接口；导入、Protocol 继承、参数及类型标注通过检查。未访问网络。
