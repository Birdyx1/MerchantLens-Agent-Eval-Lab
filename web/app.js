const $ = (id) => document.getElementById(id);
const statusNames = { pending: "待标注", one_label: "待复核", agreed: "已达成一致", disputed: "存在分歧" };
const anomalyNames = { trial_not_completed: "任务未完成", tool_failure: "工具调用失败" };
let allCandidates = [];
let summary = null;
let selectedId = null;
let loaded = false;
let loading = false;
let submitting = false;
let toastTimer;
const drafts = new Map();
const submitted = new Set();

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function taskName(candidate) { return candidate.title || candidate.task_id; }
function draftKey(id) { return JSON.stringify([$("reviewer").value.trim(), id]); }
function draftFor(id) {
  const key = draftKey(id);
  if (!drafts.has(key)) drafts.set(key, { judgment: "", root_cause: "", fix_direction: "" });
  return drafts.get(key);
}
function filteredCandidates() {
  const query = $("search").value.trim().toLowerCase();
  return allCandidates.filter((c) =>
    ($("status-filter").value === "all" || c.status === $("status-filter").value) &&
    ($("type-filter").value === "all" || c.anomaly_types.includes($("type-filter").value)) &&
    (!query || `${c.candidate_id} ${c.task_id} ${taskName(c)} ${c.anomaly_types.map((a) => anomalyNames[a] || a).join(" ")}`.toLowerCase().includes(query)));
}
function badge(status) { return `<span class="status-badge status-${esc(status)}">${esc(statusNames[status] || status)}</span>`; }
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4500);
}
function renderMetrics() {
  if (!summary) return;
  const counts = summary.status_counts;
  $("total-count").textContent = summary.total;
  $("nav-total").textContent = summary.total;
  for (const [id, status] of [["pending-count", "pending"], ["review-count", "one_label"], ["agreed-count", "agreed"]]) $(id).textContent = counts[status];
  for (const status of Object.keys(counts)) if ($(`nav-${status}`)) $(`nav-${status}`).textContent = counts[status];
  const completed = summary.reviewed;
  const progress = summary.review_progress_pct;
  $("progress-value").textContent = `${progress}%`;
  $("progress-bar").style.width = `${progress}%`;
  $("progress-caption").textContent = `${completed} / ${summary.total} 条已复核 · ${counts.disputed} 条存在分歧`;
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.status === $("status-filter").value;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}
function renderQueue() {
  const candidates = filteredCandidates();
  if (!candidates.some((c) => c.candidate_id === selectedId)) selectedId = candidates[0]?.candidate_id ?? null;
  $("queue-count").textContent = candidates.length;
  $("queue-footer").textContent = `显示 ${candidates.length} / ${allCandidates.length} 条候选 · 草稿在本次会话保留`;
  if (!candidates.length) {
    $("list").innerHTML = `<div class="empty-state"><span class="empty-symbol">⌕</span><h3>${allCandidates.length ? "没有匹配的候选" : "暂无候选数据"}</h3><p>${allCandidates.length ? "尝试调整关键词或筛选条件。" : "候选生成后，点击刷新数据开始标注。"}</p>${allCandidates.length ? '<button class="button secondary" id="clear-filters">清除筛选</button>' : ""}</div>`;
    $("clear-filters")?.addEventListener("click", () => {
      $("search").value = ""; $("status-filter").value = "all"; $("type-filter").value = "all"; render();
    });
    return;
  }
  $("list").innerHTML = candidates.map((c, index) => `<button class="candidate-row ${c.candidate_id === selectedId ? "selected" : ""}" data-index="${index}" aria-pressed="${c.candidate_id === selectedId}"><span class="candidate-topline"><span class="candidate-name">${esc(taskName(c))}</span>${badge(c.status)}</span><span class="candidate-id" title="${esc(c.task_id)}">${esc(c.task_id)}</span><span class="candidate-meta"><span>${esc(c.anomaly_types.map((a) => anomalyNames[a] || a).join(" · "))}</span><span class="label-count">${c.label_count || 0} 份标注</span></span></button>`).join("");
  $("list").querySelectorAll(".candidate-row").forEach((button) => button.addEventListener("click", () => {
    selectedId = candidates[Number(button.dataset.index)].candidate_id;
    renderQueue(); renderDetail();
  }));
}
function renderDetail() {
  const candidates = filteredCandidates();
  const candidate = candidates.find((c) => c.candidate_id === selectedId);
  if (!candidate) {
    $("detail").innerHTML = '<div class="empty-state"><span class="empty-symbol">▧</span><h3>当前没有可审阅的任务</h3><p>选择其他状态或调整搜索条件，继续审阅候选。</p></div>';
    return;
  }
  const index = candidates.indexOf(candidate);
  const draft = draftFor(selectedId);
  const alreadySubmitted = submitted.has(draftKey(selectedId));
  const evidence = candidate;
  $("detail").innerHTML = `
    <div class="detail-header"><div><div class="detail-kicker">候选详情 <span>／</span> ${badge(candidate.status)}</div><h2 class="detail-title">${esc(taskName(candidate))}</h2><p class="detail-task-id">${esc(candidate.task_id)}</p></div><div class="task-pager"><span>${index + 1} / ${candidates.length}</span><button class="icon-button" id="prev" aria-label="上一条候选" ${index === 0 ? "disabled" : ""}>‹</button><button class="icon-button" id="next" aria-label="下一条候选" ${index === candidates.length - 1 ? "disabled" : ""}>›</button></div></div>
    <form id="annotation-form"><div class="detail-body"><h3 class="section-title"><span class="step-number">01</span> 检查异常信息</h3>
    ${candidate.anomaly_types.map((type) => `<div class="anomaly-box"><span class="anomaly-icon" aria-hidden="true">⚠</span><div><strong>${esc(anomalyNames[type] || type)}</strong><p>${esc(type)}</p></div></div>`).join("")}
    <details class="evidence"><summary>查看候选原始数据 <span> · ${candidate.anomaly_types.length} 项异常</span></summary><div class="evidence-content"><pre>${esc(JSON.stringify(evidence, null, 2))}</pre>${candidate.final_answer == null ? '<p class="source-note">该候选未附带原始回答；需要时请结合对应评估记录审阅。</p>' : ""}</div></details>
    <h3 class="section-title"><span class="step-number">02</span> 记录你的判断</h3>
    <div class="judgment-options"><label class="judgment-option"><input type="radio" name="judgment" value="yes" required ${draft.judgment === "yes" ? "checked" : ""} ${alreadySubmitted ? "disabled" : ""}/><span><strong>确认为真实问题</strong><small>需要分析根因并改进</small></span></label><label class="judgment-option"><input type="radio" name="judgment" value="no" required ${draft.judgment === "no" ? "checked" : ""} ${alreadySubmitted ? "disabled" : ""}/><span><strong>非真实问题</strong><small>误报或符合预期的行为</small></span></label></div>
    <div class="fields"><div class="field"><label for="root-cause">根因分析<span>必填</span></label><textarea id="root-cause" name="root_cause" required maxlength="10000" placeholder="是什么导致了这个结果？&#10;例如：工具参数缺少有效性校验" ${alreadySubmitted ? "disabled" : ""}>${esc(draft.root_cause)}</textarea></div><div class="field"><label for="fix-direction">修复方向<span>必填</span></label><textarea id="fix-direction" name="fix_direction" required maxlength="10000" placeholder="可以怎样改进？&#10;例如：调用前校验参数，缺失时先澄清" ${alreadySubmitted ? "disabled" : ""}>${esc(draft.fix_direction)}</textarea></div></div><div class="form-message" id="form-message" role="status" aria-live="polite"></div></div>
    <div class="detail-bottom"><div class="save-note" id="draft-note">${alreadySubmitted ? "本次会话已提交 · 不可重复提交" : "独立判断，认真记录。"}<br><strong>提交后不可覆盖</strong></div><div class="submit-actions"><span class="shortcut">⌘ / Ctrl + Enter</span><button type="submit" class="button primary" id="submit-button" ${alreadySubmitted || submitting ? "disabled" : ""}>${alreadySubmitted ? "已提交 ✓" : "提交标注 →"}</button></div></div></form>`;
  $("prev").addEventListener("click", () => selectRelative(-1));
  $("next").addEventListener("click", () => selectRelative(1));
  $("annotation-form").addEventListener("input", () => {
    draft.judgment = document.querySelector('input[name="judgment"]:checked')?.value || "";
    draft.root_cause = $("root-cause").value;
    draft.fix_direction = $("fix-direction").value;
    $("draft-note").innerHTML = '草稿已保留在本次会话<br><strong>提交后不可覆盖</strong>';
  });
  $("annotation-form").addEventListener("submit", submit);
}
function selectRelative(offset) {
  const candidates = filteredCandidates();
  const index = candidates.findIndex((c) => c.candidate_id === selectedId);
  if (candidates[index + offset]) { selectedId = candidates[index + offset].candidate_id; renderQueue(); renderDetail(); }
}
function render() { renderMetrics(); renderQueue(); renderDetail(); }

async function submit(event) {
  event.preventDefault();
  if (submitting || !selectedId) return;
  const candidateId = selectedId;
  const reviewer = $("reviewer").value.trim();
  const key = draftKey(candidateId);
  const draft = { ...draftFor(candidateId) };
  const message = $("form-message");
  if (!reviewer || !/^[a-zA-Z0-9_-]+$/.test(reviewer)) { message.textContent = "请输入有效标注者 ID，仅使用字母、数字、下划线或短横线。"; $("reviewer").focus(); return; }
  if (!draft.judgment || !draft.root_cause.trim() || !draft.fix_direction.trim()) { message.textContent = "请选择判断结果，并填写根因分析与修复方向。"; return; }
  submitting = true;
  $("submit-button").disabled = true;
  $("submit-button").textContent = "正在提交…";
  message.textContent = "";
  try {
    const response = await fetch("/api/labels", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_id: candidateId, reviewer_id: reviewer, is_real_badcase: draft.judgment === "yes", root_cause: draft.root_cause.trim(), fix_direction: draft.fix_direction.trim() }) });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 409) submitted.add(key);
      throw new Error(typeof data.detail === "string" ? data.detail : "提交失败，请检查输入后重试。");
    }
    submitted.add(key);
    drafts.delete(key);
    toast("标注已保存，可以继续审阅下一条候选。");
    await load(false);
  } catch (error) {
    if (candidateId === selectedId && $("form-message")) $("form-message").textContent = error.message || "连接失败，请稍后重试。";
    else toast(error.message || "提交失败，请重试。");
  } finally {
    submitting = false;
    if ($("submit-button")) {
      const saved = submitted.has(draftKey(selectedId));
      $("submit-button").disabled = saved;
      $("submit-button").textContent = saved ? "已提交 ✓" : "提交标注 →";
    }
  }
}
async function load(announce = false) {
  if (loading) return;
  loading = true;
  $("refresh").disabled = true;
  $("sync-state").textContent = "正在同步数据…";
  try {
    const response = await fetch("/api/candidates", { cache: "no-store" });
    if (!response.ok) throw new Error(`数据加载失败（${response.status}）`);
    const data = await response.json();
    if (!Array.isArray(data.candidates) || !data.summary?.status_counts) throw new Error("候选数据格式无效，请确认后端已更新并重启。");
    allCandidates = data.candidates;
    summary = data.summary;
    const previousType = $("type-filter").value;
    const types = [...new Set(allCandidates.flatMap((c) => c.anomaly_types))].sort();
    $("type-filter").innerHTML = '<option value="all">全部异常类型</option>' + types.map((type) => `<option value="${esc(type)}">${esc(anomalyNames[type] || type)}</option>`).join("");
    $("type-filter").value = types.includes(previousType) ? previousType : "all";
    loaded = true;
    render();
    $("export").disabled = !allCandidates.length;
    $("sync-state").textContent = `已同步 · ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
    if (announce) toast("候选数据已更新，未提交的草稿已保留。");
  } catch (error) {
    $("sync-state").textContent = "同步失败 · 点击刷新重试";
    if (!loaded) {
      $("list").innerHTML = `<div class="empty-state"><span class="empty-symbol">!</span><h3>暂时无法加载数据</h3><p>${esc(error.message)}</p><button class="button secondary" id="retry">重新加载</button></div>`;
      $("retry").addEventListener("click", () => load());
    }
    toast(`同步失败：${error.message}`);
  } finally { loading = false; $("refresh").disabled = false; }
}

$("search").addEventListener("input", render);
$("status-filter").addEventListener("change", render);
$("type-filter").addEventListener("change", render);
$("reviewer").addEventListener("change", renderDetail);
$("navigation").addEventListener("click", (event) => {
  const button = event.target.closest("[data-status]");
  if (button) { $("status-filter").value = button.dataset.status; render(); }
});
$("refresh").addEventListener("click", () => load(true));
$("export").disabled = true;
$("export").addEventListener("click", () => {
  const candidates = filteredCandidates();
  const url = URL.createObjectURL(new Blob([JSON.stringify({ exported_at: new Date().toISOString(), candidates }, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = "annotation-candidates.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(`已导出当前筛选的 ${candidates.length} 条候选。`);
});
document.addEventListener("keydown", (event) => {
  const editing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (event.key === "/" && !editing && !event.ctrlKey && !event.metaKey) { event.preventDefault(); $("search").focus(); }
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); if (!$("submit-button")?.disabled) $("annotation-form")?.requestSubmit(); }
});
window.addEventListener("beforeunload", (event) => {
  if (submitting || [...drafts.values()].some((d) => d.judgment || d.root_cause || d.fix_direction)) { event.preventDefault(); event.returnValue = ""; }
});
load();
