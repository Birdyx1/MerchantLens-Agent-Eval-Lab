# 2.6g 三工具 Trace 集成验收

状态：已通过（教师实现）。

[2.6 总览](lesson06.md) · [阶段文档](README.md) · [总计划](../../plan.md)

## 知识点与架构

单工具测试只能证明局部包装正确。集成验收需要同一客户端连续调用 SQL、搜索、Python，再核对父子关系、操作 ID、结果类别与证据内容。单条 Span 的 JSON Schema 检查与跨记录检查互补：前者看字段结构，后者看整条 Trace 的关联关系。

## 实践产物

教师新增 `tests/test_three_tool_trace.py`：用临时 SQLite、模拟搜索服务和模拟 Python 执行器构造同一 MCP 服务；三个观测包装依次调用，写入同一个 JSONL 文件，并添加父 Span。使用 Draft 2020-12 Schema 校验每条记录，再校验 Trace ID 一致、Span ID 不重复、父子引用、三个独立 operation ID、结果及证据快照。`jsonschema` 已声明为测试依赖。

## 验收标准与结果

- 四条 Span 均通过当前 JSON Schema；跨记录基础检查通过。
- 三工具各有独立 Span，共用一个 Trace 与父 Span。
- SQL 金额、搜索 URL 与 Python stdout 在 Trace 中可检查。
- 全套 pytest：45 passed。

## 面试考点与踩坑

- 当前 `validate_trace` 只检查 Trace ID 一致和 Span ID 去重；父节点存在性、时间顺序、重试语义仍靠本课集成断言，尚未形成通用验证器。
- 真实 stdio 三工具发现已验收，但搜索与 Python 的**跨进程实际调用**仍未验收；本课使用进程内 MCP 和模拟依赖。
- 当前 Trace 存储原始查询、代码与输出，仅适用于本地受控数据；生产脱敏和访问控制仍待实现。

## 提交与评审记录

- 2026-11-01：教师实现并验证，本课通过。阶段 2 复盘与跨进程实调用验收待后续。
