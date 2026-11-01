# 2.3c Python 执行结果契约

状态：已通过。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：15—20 分钟。目标：定义执行结果的数据结构。

## 知识点

评测需要区分代码运行失败、超时和执行环境故障。将状态和输出结构化后，Agent 可以据此决定是否重试，评测器也能分别统计失败原因。

本课字段和状态是项目约定，不是 Docker 或 MCP 的官方结果格式。当前工具环境无法访问 Docker 守护进程，本课只定义数据，不执行代码。

## 实践任务

创建 `src/merchant_agent/tools/python_result.py`，使用 Python 标准库的 `dataclasses.dataclass` 定义 `PythonRunResult`：

| 字段 | 类型 | 含义 |
|---|---|---|
| status | str | succeeded、program_error、timeout 或 infrastructure_error |
| stdout | str | 标准输出 |
| stderr | str | 标准错误 |
| exit_code | int 或 None | 能取得时记录退出码；否则为 None |
| duration_ms | int | 执行耗时，毫秒 |
| stdout_truncated | bool | 标准输出是否被截断 |
| stderr_truncated | bool | 标准错误是否被截断 |

字段均由调用方提供，不需要默认值。本课只定义数据结构，不实现执行、截断或字段运行时校验。

## 验收标准

1. 能创建成功、程序报错和超时三种模拟结果，并通过属性读取所有字段。
2. 使用 `dataclasses.asdict` 后得到包含七个字段的字典，可用标准库 `json.dumps` 序列化。
3. 示例数据为模拟值；不能因此宣称代码已经运行在隔离环境中。

## 面试考点与踩坑

- 代码本身异常和容器启动失败不是同一类问题，重试和归因方式可能不同。
- 空输出不表示输出未被截断，需结合截断标记看。
- Python 类型注解本身不会自动验证运行时输入；本课不要求实现校验器。

## 提交与评审记录

- 2026-11-01：已开课，等待学员提交；尚未评审或验收。
- 首次评审：七个字段、类型注解与 dataclass 正确；用当前类构造成功、程序错误、超时三种模拟对象，属性读取和 asdict/JSON 序列化均通过。
- 待修正：类名是 PythonRequest，而约定接口为 PythonRunResult；按约定导入类会失败。未代改，等待修订后复评。
- 2026-11-01 复评：学员将类名改为 PythonRunResult；成功、程序错误、超时三个模拟对象的字段和 JSON 序列化验证通过，本课完成。
- Docker 只读检查：当前受限工具环境无法访问 socket；在授权的沙箱外检查时，客户端和服务端均为 29.5.3，所需 `python:3.13-alpine` 镜像尚未在本机找到。未拉取镜像或运行容器。
- 2026-11-01：教师扩展可选 `oom_killed: bool | None` 字段，记录 Docker 状态；保留原有七个必填字段及构造兼容性。
