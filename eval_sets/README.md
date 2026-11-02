# 评测集目录

四个目录分别保存 Golden、Regression、线上回流 Badcase、Negative Task。每个 Task 只能属于一个集合；入库使用 `EvalSetStore.register`，不得手工复制跨集合。`fixtures/eval_task_examples/` 是草稿示例，不属于任何正式集合。

`badcase` 的物理隔离不等于脱敏完成；真实线上数据须先经过后续 9.2 脱敏与复核。Holdout 在 4.6 建立独立受控位置。
