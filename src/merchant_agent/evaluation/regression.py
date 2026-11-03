"""修复回测与派生回归：确认修复生效，并把 badcase 固化成回归任务。"""


def verify_fix(*, before_passed: bool, after_passed: bool) -> dict:
    """修复回测：修复前必须失败，修复后必须通过。"""
    if before_passed:
        raise ValueError("修复前已通过，不是可回测的 badcase")
    return {
        "fixed": after_passed,
        "status": "fixed" if after_passed else "not_fixed",
    }


def derive_regression(task: dict) -> dict:
    """把已裁决的 badcase 派生成回归任务，保留评测契约并标记来源。"""
    if task.get("label_status") != "adjudicated":
        raise ValueError("只有已裁决（adjudicated）的 badcase 才能派生回归")
    return {
        **task,
        "task_id": f"regression_{task['task_id']}",
        "provenance": {"kind": "regression", "source_ref": task["task_id"]},
    }
