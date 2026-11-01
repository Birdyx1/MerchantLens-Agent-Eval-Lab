# 2.3b Python 执行隔离：构造启动参数

状态：已通过（教师协助修复导入配置）。

[阶段文档](README.md) · [总计划](../../plan.md)

建议用时：20—30 分钟。目标：构造固定的 Docker 参数列表，不启动容器。

## 知识点

容器可以配置网络、内存、CPU、进程数和文件系统限制，但这些设置需要实际运行和验证，不能仅凭参数列表宣称执行环境安全。[Docker run 官方文档](https://docs.docker.com/reference/cli/docker/container/run/)、[Docker 安全文档](https://docs.docker.com/engine/security/)

受限工具环境访问 Docker 守护进程时被拒绝，沙箱外只读检查可访问。本课只构造列表；2.3d 验证环境，真实运行器及隔离验证在 2.3h 实施。

## 实践任务

创建 `src/merchant_agent/tools/python_command.py`，实现：

```python
def build_docker_args(code: str, timeout_seconds: int) -> list[str]:
    ...
```

先调用上一课的 `validate_python_request`，无效请求让 ValueError 传出。有效时返回参数列表，用于表达以下固定设置：

| 设置 | Docker 参数 |
|---|---|
| 容器退出后清理 | `--rm` |
| 不使用容器网络 | `--network none` |
| 内存和 CPU 上限 | `--memory 128m`、`--cpus 0.5` |
| 进程数上限 | `--pids-limit 64` |
| 容器根文件系统只读 | `--read-only` |
| 不添加 Linux capabilities | `--cap-drop ALL` |
| 无特权用户 | `--user 65534:65534` |
| 不自动拉取镜像 | `--pull never` |

参数列表以 `docker`、`run` 开始，选项后依次为固定镜像 `python:3.13-alpine`、`python`、`-I`、`-c` 和原始 `code`。每个选项及其值各占一个列表元素；不接受调用方自定义 Docker 参数或挂载，不执行该列表。

## 验收标准

1. 有效输入返回 list[str]，参数和顺序符合上述约定；code 原样作为最后一个元素。
2. 包含空格、引号或换行的 code 仍是单独一个元素。
3. 无效 code 或超时抛出 ValueError，复用上一课的检查。
4. 不调用 subprocess 或 Docker；本课不声称实际执行、隔离、超时或清理已经实现。

## 面试考点与踩坑

- 不拼成 shell 字符串；参数列表方便后续以 `shell=False` 传递，避免将代码内容当作宿主机 shell 语法解释。
- `timeout_seconds` 在本课只校验，不会实际限制运行时间；运行器必须另行实现超时及容器终止。
- `--rm` 在容器退出时清理，不能替代对超时容器的主动终止和核验。镜像标签还需在实际实验前固定为可核验的版本。
- 不将 Docker socket、宿主目录或敏感凭证挂入不可信执行环境。仅有容器选项不能证明达到生产安全要求。

## 提交与评审记录

- 2026-11-01：已开课，等待学员提交；Docker 守护进程在当前工具环境不可访问，本课无需实际运行。
- 首次评审：参数内容与顺序、含引号换行的代码及无效输入检查均通过；没有启动 Docker。
- 第 1 行使用 `from src.merchant_agent...`，在仓库根目录可能因工作目录恰好在搜索路径中而通过；从仓库外只将 `src` 加入 PYTHONPATH 时实际触发 ModuleNotFoundError。需改为 `from merchant_agent.tools.python_request import validate_python_request` 后复测。
- 未代改学员文件，等待修订。隔离和超时尚未实际验证。
- 2026-11-01：学员反馈更改导入后找不到模块；检查发现 IDE 的 src 尚未设置为源码根目录。教师应请求修正导入并配置本地 IDE；从仓库外设置 PYTHONPATH 后验证导入、参数和无效输入通过。IDE 界面是否刷新未验证。
- 课时通过；未运行 Docker，实际隔离、超时及清理仍待 2.3h 验证。
