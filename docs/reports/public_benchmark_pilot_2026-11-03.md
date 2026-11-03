# BFCL / BIRD 固定子集实验

运行状态：**completed**；Run ID：`5782c93272104971a7b82e2453ba8160`。

这是公开基准子集上的项目适配实验，不能与官方全量排行榜直接比较。BFCL 使用统一 JSON prompting，未使用官方模型 handler 或原生 function calling。BIRD 使用官方 EX 函数（结果行集合完全相等），不增加浮点容差或列名判据。

## 冻结协议

- 清单 SHA256：`ce763946d6a77b046929dd1f61ff6d4127c1e19bef87cd44e8c2439833db7a3a`。
- 每个单元每题重复 3 次；总计划 240 个 Trial，已记录 240 个。
- BFCL：simple_python / multiple / parallel / irrelevance 各 5 题，两个模型使用相同题目与提示。
- BIRD：5 个 SQLite 数据库各 4 题；同一 DeepSeek 模型对比 direct / react。公开 evidence 和完整 Schema 均提供，参考 SQL 从不进入模型上下文。
- temperature=0；每次输出上限 2048；API 超时 90s；ReAct 最多 5 次模型调用，累计输入输出预算 24000。无自动重试，不删除失败 Trial。
- BIRD 数据库只读；工具预览最多 20 行，但 EX 在完整结果上执行。最终评分查询不算 Agent 工具调用。
- BFCL 原官方 Python checker 函数体保持不变，仅隔离无关 SDK 和 Java/JS 导入；irrelevance 以空调用数组判定。

## 结果

| 基准 | 模型 / 配置 | 成功 / Trial | 成功率 | 每题三次均成功 | 平均耗时 s | P95 s | 平均 Token | 模型调用 | 工具调用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bfcl | deepseek / json_prompt | 53/60 | 88.3% | 85.0% | 1.26 | 1.90 | 468 | 1.00 | 0.00 |
| bfcl | glm / json_prompt | 49/60 | 81.7% | 75.0% | 5.13 | 11.16 | 539 | 1.00 | 0.00 |
| bird | deepseek / direct | 22/60 | 36.7% | 30.0% | 5.68 | 12.89 | 1472 | 1.00 | 0.00 |
| bird | deepseek / react | 17/60 | 28.3% | 10.0% | 5.68 | 12.57 | 2527 | 1.78 | 0.82 |

## 实际模型标识

```json
{
  "deepseek": {
    "requested": "deepseek-flash",
    "interface": "responses",
    "enable_thinking": "provider default",
    "returned": [
      "deepseek-flash"
    ]
  },
  "glm": {
    "requested": "zai-org/GLM-5.3-Flash",
    "interface": "chat_completions",
    "enable_thinking": false,
    "returned": [
      "zai-org/GLM-5.3-Flash"
    ]
  }
}
```

## 失败分型与分层结果

### bfcl / deepseek / json_prompt

```json
{
  "failures": {
    "unnecessary_tool_call": 5,
    "format_error": 1,
    "multiple_function_checker:wrong_count": 1
  },
  "categories": {
    "irrelevance": {
      "trials": 15,
      "successes": 9
    },
    "multiple": {
      "trials": 15,
      "successes": 14
    },
    "parallel": {
      "trials": 15,
      "successes": 15
    },
    "simple_python": {
      "trials": 15,
      "successes": 15
    }
  },
  "token_observed_trials": 60
}
```

### bfcl / glm / json_prompt

```json
{
  "failures": {
    "unnecessary_tool_call": 10,
    "multiple_function_checker:wrong_count": 1
  },
  "categories": {
    "irrelevance": {
      "trials": 15,
      "successes": 5
    },
    "multiple": {
      "trials": 15,
      "successes": 14
    },
    "parallel": {
      "trials": 15,
      "successes": 15
    },
    "simple_python": {
      "trials": 15,
      "successes": 15
    }
  },
  "token_observed_trials": 60
}
```

### bird / deepseek / direct

```json
{
  "failures": {
    "execution_mismatch": 29,
    "model_or_runner_error": 9
  },
  "categories": {
    "challenging": {
      "trials": 24,
      "successes": 6
    },
    "moderate": {
      "trials": 30,
      "successes": 13
    },
    "simple": {
      "trials": 6,
      "successes": 3
    }
  },
  "token_observed_trials": 51
}
```

### bird / deepseek / react

```json
{
  "failures": {
    "format_error": 20,
    "execution_mismatch": 14,
    "step_budget": 2,
    "model_or_runner_error": 7
  },
  "categories": {
    "challenging": {
      "trials": 24,
      "successes": 7
    },
    "moderate": {
      "trials": 30,
      "successes": 7
    },
    "simple": {
      "trials": 6,
      "successes": 3
    }
  },
  "token_observed_trials": 53
}
```

## 配对差值

按题目配对 Bootstrap，区间仅描述当前固定子集的不确定性，不能外推总体。

```json
{
  "bfcl": {
    "left": "deepseek/json_prompt",
    "right": "glm/json_prompt",
    "right_minus_left": -0.06666666666666667,
    "task_bootstrap_95_interval": [
      -0.2,
      0.03333333333333333
    ],
    "tasks": 20,
    "seed": 20261103,
    "draws": 2000
  },
  "bird": {
    "left": "deepseek/direct",
    "right": "deepseek/react",
    "right_minus_left": -0.08333333333333333,
    "task_bootstrap_95_interval": [
      -0.3,
      0.11666666666666665
    ],
    "tasks": 20,
    "seed": 20261103,
    "draws": 2000
  }
}
```

## 逐题记录

| 基准 | ID | 模型 / 配置 | 重复 | 通过 | 失败类型 |
|---|---|---|---:|---|---|
| bfcl | irrelevance_109 | deepseek / json_prompt | 0 | True | — |
| bfcl | irrelevance_109 | deepseek / json_prompt | 1 | True | — |
| bfcl | irrelevance_109 | deepseek / json_prompt | 2 | True | — |
| bfcl | irrelevance_109 | glm / json_prompt | 0 | False | unnecessary_tool_call |
| bfcl | irrelevance_109 | glm / json_prompt | 1 | False | unnecessary_tool_call |
| bfcl | irrelevance_109 | glm / json_prompt | 2 | False | unnecessary_tool_call |
| bfcl | irrelevance_113 | deepseek / json_prompt | 0 | False | unnecessary_tool_call |
| bfcl | irrelevance_113 | deepseek / json_prompt | 1 | False | format_error |
| bfcl | irrelevance_113 | deepseek / json_prompt | 2 | False | unnecessary_tool_call |
| bfcl | irrelevance_113 | glm / json_prompt | 0 | False | unnecessary_tool_call |
| bfcl | irrelevance_113 | glm / json_prompt | 1 | False | unnecessary_tool_call |
| bfcl | irrelevance_113 | glm / json_prompt | 2 | False | unnecessary_tool_call |
| bfcl | irrelevance_139 | deepseek / json_prompt | 0 | True | — |
| bfcl | irrelevance_139 | deepseek / json_prompt | 1 | True | — |
| bfcl | irrelevance_139 | deepseek / json_prompt | 2 | True | — |
| bfcl | irrelevance_139 | glm / json_prompt | 0 | True | — |
| bfcl | irrelevance_139 | glm / json_prompt | 1 | True | — |
| bfcl | irrelevance_139 | glm / json_prompt | 2 | True | — |
| bfcl | irrelevance_183 | deepseek / json_prompt | 0 | False | unnecessary_tool_call |
| bfcl | irrelevance_183 | deepseek / json_prompt | 1 | False | unnecessary_tool_call |
| bfcl | irrelevance_183 | deepseek / json_prompt | 2 | False | unnecessary_tool_call |
| bfcl | irrelevance_183 | glm / json_prompt | 0 | True | — |
| bfcl | irrelevance_183 | glm / json_prompt | 1 | False | unnecessary_tool_call |
| bfcl | irrelevance_183 | glm / json_prompt | 2 | False | unnecessary_tool_call |
| bfcl | irrelevance_60 | deepseek / json_prompt | 0 | True | — |
| bfcl | irrelevance_60 | deepseek / json_prompt | 1 | True | — |
| bfcl | irrelevance_60 | deepseek / json_prompt | 2 | True | — |
| bfcl | irrelevance_60 | glm / json_prompt | 0 | True | — |
| bfcl | irrelevance_60 | glm / json_prompt | 1 | False | unnecessary_tool_call |
| bfcl | irrelevance_60 | glm / json_prompt | 2 | False | unnecessary_tool_call |
| bfcl | multiple_111 | deepseek / json_prompt | 0 | True | — |
| bfcl | multiple_111 | deepseek / json_prompt | 1 | True | — |
| bfcl | multiple_111 | deepseek / json_prompt | 2 | True | — |
| bfcl | multiple_111 | glm / json_prompt | 0 | True | — |
| bfcl | multiple_111 | glm / json_prompt | 1 | True | — |
| bfcl | multiple_111 | glm / json_prompt | 2 | True | — |
| bfcl | multiple_118 | deepseek / json_prompt | 0 | True | — |
| bfcl | multiple_118 | deepseek / json_prompt | 1 | True | — |
| bfcl | multiple_118 | deepseek / json_prompt | 2 | True | — |
| bfcl | multiple_118 | glm / json_prompt | 0 | True | — |
| bfcl | multiple_118 | glm / json_prompt | 1 | True | — |
| bfcl | multiple_118 | glm / json_prompt | 2 | True | — |
| bfcl | multiple_131 | deepseek / json_prompt | 0 | True | — |
| bfcl | multiple_131 | deepseek / json_prompt | 1 | True | — |
| bfcl | multiple_131 | deepseek / json_prompt | 2 | True | — |
| bfcl | multiple_131 | glm / json_prompt | 0 | True | — |
| bfcl | multiple_131 | glm / json_prompt | 1 | True | — |
| bfcl | multiple_131 | glm / json_prompt | 2 | True | — |
| bfcl | multiple_191 | deepseek / json_prompt | 0 | True | — |
| bfcl | multiple_191 | deepseek / json_prompt | 1 | True | — |
| bfcl | multiple_191 | deepseek / json_prompt | 2 | True | — |
| bfcl | multiple_191 | glm / json_prompt | 0 | True | — |
| bfcl | multiple_191 | glm / json_prompt | 1 | True | — |
| bfcl | multiple_191 | glm / json_prompt | 2 | True | — |
| bfcl | multiple_25 | deepseek / json_prompt | 0 | False | multiple_function_checker:wrong_count |
| bfcl | multiple_25 | deepseek / json_prompt | 1 | True | — |
| bfcl | multiple_25 | deepseek / json_prompt | 2 | True | — |
| bfcl | multiple_25 | glm / json_prompt | 0 | False | multiple_function_checker:wrong_count |
| bfcl | multiple_25 | glm / json_prompt | 1 | True | — |
| bfcl | multiple_25 | glm / json_prompt | 2 | True | — |
| bfcl | parallel_161 | deepseek / json_prompt | 0 | True | — |
| bfcl | parallel_161 | deepseek / json_prompt | 1 | True | — |
| bfcl | parallel_161 | deepseek / json_prompt | 2 | True | — |
| bfcl | parallel_161 | glm / json_prompt | 0 | True | — |
| bfcl | parallel_161 | glm / json_prompt | 1 | True | — |
| bfcl | parallel_161 | glm / json_prompt | 2 | True | — |
| bfcl | parallel_197 | deepseek / json_prompt | 0 | True | — |
| bfcl | parallel_197 | deepseek / json_prompt | 1 | True | — |
| bfcl | parallel_197 | deepseek / json_prompt | 2 | True | — |
| bfcl | parallel_197 | glm / json_prompt | 0 | True | — |
| bfcl | parallel_197 | glm / json_prompt | 1 | True | — |
| bfcl | parallel_197 | glm / json_prompt | 2 | True | — |
| bfcl | parallel_22 | deepseek / json_prompt | 0 | True | — |
| bfcl | parallel_22 | deepseek / json_prompt | 1 | True | — |
| bfcl | parallel_22 | deepseek / json_prompt | 2 | True | — |
| bfcl | parallel_22 | glm / json_prompt | 0 | True | — |
| bfcl | parallel_22 | glm / json_prompt | 1 | True | — |
| bfcl | parallel_22 | glm / json_prompt | 2 | True | — |
| bfcl | parallel_76 | deepseek / json_prompt | 0 | True | — |
| bfcl | parallel_76 | deepseek / json_prompt | 1 | True | — |
| bfcl | parallel_76 | deepseek / json_prompt | 2 | True | — |
| bfcl | parallel_76 | glm / json_prompt | 0 | True | — |
| bfcl | parallel_76 | glm / json_prompt | 1 | True | — |
| bfcl | parallel_76 | glm / json_prompt | 2 | True | — |
| bfcl | parallel_96 | deepseek / json_prompt | 0 | True | — |
| bfcl | parallel_96 | deepseek / json_prompt | 1 | True | — |
| bfcl | parallel_96 | deepseek / json_prompt | 2 | True | — |
| bfcl | parallel_96 | glm / json_prompt | 0 | True | — |
| bfcl | parallel_96 | glm / json_prompt | 1 | True | — |
| bfcl | parallel_96 | glm / json_prompt | 2 | True | — |
| bfcl | simple_python_171 | deepseek / json_prompt | 0 | True | — |
| bfcl | simple_python_171 | deepseek / json_prompt | 1 | True | — |
| bfcl | simple_python_171 | deepseek / json_prompt | 2 | True | — |
| bfcl | simple_python_171 | glm / json_prompt | 0 | True | — |
| bfcl | simple_python_171 | glm / json_prompt | 1 | True | — |
| bfcl | simple_python_171 | glm / json_prompt | 2 | True | — |
| bfcl | simple_python_186 | deepseek / json_prompt | 0 | True | — |
| bfcl | simple_python_186 | deepseek / json_prompt | 1 | True | — |
| bfcl | simple_python_186 | deepseek / json_prompt | 2 | True | — |
| bfcl | simple_python_186 | glm / json_prompt | 0 | True | — |
| bfcl | simple_python_186 | glm / json_prompt | 1 | True | — |
| bfcl | simple_python_186 | glm / json_prompt | 2 | True | — |
| bfcl | simple_python_25 | deepseek / json_prompt | 0 | True | — |
| bfcl | simple_python_25 | deepseek / json_prompt | 1 | True | — |
| bfcl | simple_python_25 | deepseek / json_prompt | 2 | True | — |
| bfcl | simple_python_25 | glm / json_prompt | 0 | True | — |
| bfcl | simple_python_25 | glm / json_prompt | 1 | True | — |
| bfcl | simple_python_25 | glm / json_prompt | 2 | True | — |
| bfcl | simple_python_270 | deepseek / json_prompt | 0 | True | — |
| bfcl | simple_python_270 | deepseek / json_prompt | 1 | True | — |
| bfcl | simple_python_270 | deepseek / json_prompt | 2 | True | — |
| bfcl | simple_python_270 | glm / json_prompt | 0 | True | — |
| bfcl | simple_python_270 | glm / json_prompt | 1 | True | — |
| bfcl | simple_python_270 | glm / json_prompt | 2 | True | — |
| bfcl | simple_python_63 | deepseek / json_prompt | 0 | True | — |
| bfcl | simple_python_63 | deepseek / json_prompt | 1 | True | — |
| bfcl | simple_python_63 | deepseek / json_prompt | 2 | True | — |
| bfcl | simple_python_63 | glm / json_prompt | 0 | True | — |
| bfcl | simple_python_63 | glm / json_prompt | 1 | True | — |
| bfcl | simple_python_63 | glm / json_prompt | 2 | True | — |
| bird | bird_297 | deepseek / direct | 0 | True | — |
| bird | bird_297 | deepseek / direct | 1 | True | — |
| bird | bird_297 | deepseek / direct | 2 | True | — |
| bird | bird_297 | deepseek / react | 0 | True | — |
| bird | bird_297 | deepseek / react | 1 | True | — |
| bird | bird_297 | deepseek / react | 2 | True | — |
| bird | bird_299 | deepseek / direct | 0 | True | — |
| bird | bird_299 | deepseek / direct | 1 | False | model_or_runner_error |
| bird | bird_299 | deepseek / direct | 2 | True | — |
| bird | bird_299 | deepseek / react | 0 | False | format_error |
| bird | bird_299 | deepseek / react | 1 | False | format_error |
| bird | bird_299 | deepseek / react | 2 | False | format_error |
| bird | bird_3 | deepseek / direct | 0 | True | — |
| bird | bird_3 | deepseek / direct | 1 | True | — |
| bird | bird_3 | deepseek / direct | 2 | True | — |
| bird | bird_3 | deepseek / react | 0 | False | model_or_runner_error |
| bird | bird_3 | deepseek / react | 1 | False | execution_mismatch |
| bird | bird_3 | deepseek / react | 2 | False | format_error |
| bird | bird_300 | deepseek / direct | 0 | True | — |
| bird | bird_300 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_300 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_300 | deepseek / react | 0 | True | — |
| bird | bird_300 | deepseek / react | 1 | True | — |
| bird | bird_300 | deepseek / react | 2 | True | — |
| bird | bird_313 | deepseek / direct | 0 | True | — |
| bird | bird_313 | deepseek / direct | 1 | True | — |
| bird | bird_313 | deepseek / direct | 2 | True | — |
| bird | bird_313 | deepseek / react | 0 | True | — |
| bird | bird_313 | deepseek / react | 1 | False | format_error |
| bird | bird_313 | deepseek / react | 2 | True | — |
| bird | bird_336 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_336 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_336 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_336 | deepseek / react | 0 | False | format_error |
| bird | bird_336 | deepseek / react | 1 | False | step_budget |
| bird | bird_336 | deepseek / react | 2 | False | step_budget |
| bird | bird_338 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_338 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_338 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_338 | deepseek / react | 0 | False | execution_mismatch |
| bird | bird_338 | deepseek / react | 1 | False | format_error |
| bird | bird_338 | deepseek / react | 2 | False | format_error |
| bird | bird_346 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_346 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_346 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_346 | deepseek / react | 0 | False | execution_mismatch |
| bird | bird_346 | deepseek / react | 1 | False | execution_mismatch |
| bird | bird_346 | deepseek / react | 2 | True | — |
| bird | bird_35 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_35 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_35 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_35 | deepseek / react | 0 | True | — |
| bird | bird_35 | deepseek / react | 1 | False | execution_mismatch |
| bird | bird_35 | deepseek / react | 2 | False | format_error |
| bird | bird_356 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_356 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_356 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_356 | deepseek / react | 0 | False | execution_mismatch |
| bird | bird_356 | deepseek / react | 1 | True | — |
| bird | bird_356 | deepseek / react | 2 | False | execution_mismatch |
| bird | bird_383 | deepseek / direct | 0 | True | — |
| bird | bird_383 | deepseek / direct | 1 | True | — |
| bird | bird_383 | deepseek / direct | 2 | True | — |
| bird | bird_383 | deepseek / react | 0 | False | format_error |
| bird | bird_383 | deepseek / react | 1 | False | format_error |
| bird | bird_383 | deepseek / react | 2 | True | — |
| bird | bird_388 | deepseek / direct | 0 | True | — |
| bird | bird_388 | deepseek / direct | 1 | True | — |
| bird | bird_388 | deepseek / direct | 2 | True | — |
| bird | bird_388 | deepseek / react | 0 | False | execution_mismatch |
| bird | bird_388 | deepseek / react | 1 | False | format_error |
| bird | bird_388 | deepseek / react | 2 | False | format_error |
| bird | bird_4 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_4 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_4 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_4 | deepseek / react | 0 | False | model_or_runner_error |
| bird | bird_4 | deepseek / react | 1 | False | model_or_runner_error |
| bird | bird_4 | deepseek / react | 2 | False | execution_mismatch |
| bird | bird_405 | deepseek / direct | 0 | False | model_or_runner_error |
| bird | bird_405 | deepseek / direct | 1 | False | model_or_runner_error |
| bird | bird_405 | deepseek / direct | 2 | False | model_or_runner_error |
| bird | bird_405 | deepseek / react | 0 | False | model_or_runner_error |
| bird | bird_405 | deepseek / react | 1 | False | format_error |
| bird | bird_405 | deepseek / react | 2 | False | format_error |
| bird | bird_433 | deepseek / direct | 0 | False | model_or_runner_error |
| bird | bird_433 | deepseek / direct | 1 | False | model_or_runner_error |
| bird | bird_433 | deepseek / direct | 2 | False | model_or_runner_error |
| bird | bird_433 | deepseek / react | 0 | False | model_or_runner_error |
| bird | bird_433 | deepseek / react | 1 | False | model_or_runner_error |
| bird | bird_433 | deepseek / react | 2 | False | model_or_runner_error |
| bird | bird_468 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_468 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_468 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_468 | deepseek / react | 0 | True | — |
| bird | bird_468 | deepseek / react | 1 | False | execution_mismatch |
| bird | bird_468 | deepseek / react | 2 | True | — |
| bird | bird_476 | deepseek / direct | 0 | True | — |
| bird | bird_476 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_476 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_476 | deepseek / react | 0 | False | execution_mismatch |
| bird | bird_476 | deepseek / react | 1 | True | — |
| bird | bird_476 | deepseek / react | 2 | False | execution_mismatch |
| bird | bird_482 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_482 | deepseek / direct | 1 | False | model_or_runner_error |
| bird | bird_482 | deepseek / direct | 2 | False | model_or_runner_error |
| bird | bird_482 | deepseek / react | 0 | False | format_error |
| bird | bird_482 | deepseek / react | 1 | False | format_error |
| bird | bird_482 | deepseek / react | 2 | False | format_error |
| bird | bird_487 | deepseek / direct | 0 | True | — |
| bird | bird_487 | deepseek / direct | 1 | True | — |
| bird | bird_487 | deepseek / direct | 2 | True | — |
| bird | bird_487 | deepseek / react | 0 | True | — |
| bird | bird_487 | deepseek / react | 1 | False | format_error |
| bird | bird_487 | deepseek / react | 2 | True | — |
| bird | bird_7 | deepseek / direct | 0 | False | execution_mismatch |
| bird | bird_7 | deepseek / direct | 1 | False | execution_mismatch |
| bird | bird_7 | deepseek / direct | 2 | False | execution_mismatch |
| bird | bird_7 | deepseek / react | 0 | False | execution_mismatch |
| bird | bird_7 | deepseek / react | 1 | False | format_error |
| bird | bird_7 | deepseek / react | 2 | False | execution_mismatch |

## 解释边界

- 20 题/基准，非全量、非随机生产流量，不宣称排行榜成绩或总体显著提升。
- 三次全成功率是此子集的经验一致性指标，不是对真实成功概率的精确估计。
- 错误与超时纳入总体成功率分母；未知/失败请求的 Token 用量不可观测，不能当真实零成本。
- ReAct 比 direct 获得更多调用与工具访问，差异是整体配置差异，不能归因于某一句提示或模型能力。
- BIRD 仅选五个较小数据库，存在数据库选择偏差；BFCL 只含四种单轮类别，不代表多轮或 Agentic 总分。
- 此实验使用公开开发题，与项目密封 Holdout 无关；未进行真人双标，不将模型输出视为人工标签。
