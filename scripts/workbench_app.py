"""Streamlit 标注工作台原型（9.3）：浏览候选、提交标注、查看状态。"""

import json
from pathlib import Path

import streamlit as st

from merchant_agent.evaluation.workbench import Candidate, label_status, submit_label

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "runs/workbench/candidates.json"
LABELS_ROOT = ROOT / "runs/workbench"

st.set_page_config(page_title="标注工作台", layout="wide")
st.title("标注工作台")
st.caption("候选来自 9.1 异常识别 + 9.2 脱敏去重；标注不可覆盖，状态自动汇总。")

candidates = json.loads(CANDIDATES.read_text(encoding="utf-8")) if CANDIDATES.is_file() else []
if not candidates:
    st.warning("没有候选。先运行 live_sanitize_scan 生成 runs/workbench/candidates.json。")
    st.stop()

reviewer = st.sidebar.text_input("reviewer_id", "reviewer_one")
st.sidebar.metric("候选总数", len(candidates))
statuses = [label_status(Candidate(item["candidate_id"], item["task_id"],
                                   tuple(item["anomaly_types"]), None),
                         root=LABELS_ROOT)["status"] for item in candidates]
st.sidebar.write({s: statuses.count(s) for s in sorted(set(statuses))})
only_pending = st.sidebar.checkbox("只看未标注", value=False)

for item in candidates:
    candidate = Candidate(item["candidate_id"], item["task_id"],
                          tuple(item["anomaly_types"]), None)
    status = label_status(candidate, root=LABELS_ROOT)["status"]
    if only_pending and status != "pending":
        continue
    with st.expander(f"[{status}] {item['candidate_id']}"):
        st.write(f"**任务**：{item['task_id']}")
        st.write(f"**异常类型**：{', '.join(item['anomaly_types'])}")
        with st.form(f"form_{item['candidate_id']}"):
            badcase = st.checkbox("是真实 badcase（勾选=是）")
            root_cause = st.text_input("根因")
            fix_direction = st.text_input("修复方向")
            submitted = st.form_submit_button("提交标注")
        if submitted:
            try:
                submit_label(candidate, reviewer_id=reviewer, is_real_badcase=badcase,
                             root_cause=root_cause, fix_direction=fix_direction,
                             root=LABELS_ROOT)
                st.success("已提交")
                st.rerun()
            except FileExistsError:
                st.error("该候选你已提交过，不可覆盖；换 reviewer_id 或人工删除后重提。")
            except ValueError as exc:
                st.error(str(exc))
