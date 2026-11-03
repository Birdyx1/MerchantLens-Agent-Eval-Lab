# 标准评测报告：2026-11-03-multitype

生成时间：2026-11-03T14:02:53.551492+00:00

> **安全门禁：PASS**

> **退化告警：未提供**

## 数据飞轮

- 异常总数：25
  - trial_not_completed: 13
  - tool_failure: 12
- 待标注候选：14

## 复现命令

```bash
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_anomaly_scan
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_safety_gate_demo
PYTHONPATH=src .venv/bin/python -m merchant_agent.evaluation.live_standard_report
```
