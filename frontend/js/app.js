/**
 * JavaScript Controller for Enterprise Identity Service Shift-Handover Workspace
 * Handles REST API integration, dynamic graph rendering, evidence drill-down,
 * role-based perspectives, edge case simulation, and benchmark visualizations.
 */

let currentWorkspaceData = null;
let activeRole = "SRE / On-Call Specialist";

document.addEventListener("DOMContentLoaded", () => {
  fetchWorkspaceData();
  runBenchmark(); // Pre-load benchmark results
});

async function fetchWorkspaceData() {
  try {
    const res = await fetch(`/api/workspace?role=${encodeURIComponent(activeRole)}`);
    if (!res.ok) throw new Error("Failed to load workspace data");
    const data = await res.json();
    currentWorkspaceData = data;
    renderWorkspace(data);
  } catch (err) {
    console.error("Error fetching workspace:", err);
  }
}

function renderWorkspace(data) {
  // 1. Render Freshness Indicators
  renderFreshness(data.freshness);

  // 2. Render Handover Banner Meta
  document.getElementById("risk-score-display").innerText = `${data.context_loss_risk_score.toFixed(1)} / 100`;
  document.getElementById("outgoing-lead").innerText = data.outgoing_shift_lead;
  document.getElementById("incoming-lead").innerText = data.incoming_shift_lead;
  document.getElementById("handover-status-badge").innerText = data.handover_status;
  
  if (data.handover_status === "ACCEPTED") {
    document.getElementById("handover-status-badge").className = "freshness-badge badge-fresh";
  } else {
    document.getElementById("handover-status-badge").className = "freshness-badge badge-delayed";
  }

  // 3. Left Column: Operational Streams
  renderChatStream(data.raw_data_sources.chat_excerpts, data.freshness.chat_excerpts);
  renderMetricsStream(data.raw_data_sources.dashboard_metrics, data.freshness.dashboards);
  renderOwnershipStream(data.raw_data_sources.ownership_changes);

  // 4. Center Column: Hypotheses Graph & Actions Queue
  renderHypothesesGraph(data.hypotheses, data.evidence_list);
  renderActionsQueue(data.unresolved_actions, data.change_reviews);

  // 5. Shift Summary
  document.getElementById("shift-summary-text").innerText = data.shift_summary;

  // 6. Right Column: Audit Trail
  renderAuditTrail(data.audit_trail);
}

function renderFreshness(freshness) {
  const updateBadge = (elemId, state) => {
    const elem = document.getElementById(elemId);
    if (!elem) return;
    elem.innerText = state;
    if (state === "FRESH") elem.className = "freshness-badge badge-fresh";
    else if (state === "DELAYED") elem.className = "freshness-badge badge-delayed";
    else if (state === "STALE") elem.className = "freshness-badge badge-stale";
    else if (state === "MISSING") elem.className = "freshness-badge badge-missing";
  };

  updateBadge("fresh-notes", freshness.incident_notes);
  updateBadge("fresh-chat", freshness.chat_excerpts);
  updateBadge("fresh-metrics", freshness.dashboards);
  updateBadge("fresh-ownership", freshness.ownership_changes);
  updateBadge("fresh-actions", freshness.action_logs);
}

function renderChatStream(chatList, freshnessState) {
  const container = document.getElementById("chat-stream-container");
  container.innerHTML = "";

  if (freshnessState === "MISSING") {
    container.innerHTML = `
      <div style="background: rgba(239,68,68,0.15); border: 1px dashed #ef4444; padding: 10px; border-radius: 6px; font-size: 0.78rem; color: #f87171;">
        ⚠️ <strong>Chat Ingestion API Offline</strong><br>
        Workspace operating in resilient mode using cached graph evidence.
      </div>
    `;
    return;
  }

  chatList.forEach(chat => {
    const div = document.createElement("div");
    div.className = "stream-item";
    div.innerHTML = `
      <div class="stream-meta">
        <span style="font-weight: 700; color: var(--accent-cyan);">${chat.sender} (${chat.sender_role})</span>
        <span>${chat.timestamp.substring(11, 19)} UTC</span>
      </div>
      <div class="chat-text">${chat.text}</div>
      ${chat.key_takeaway ? `<div class="key-takeaway">💡 ${chat.key_takeaway}</div>` : ""}
    `;
    container.appendChild(div);
  });
}

function renderMetricsStream(metricsList, freshnessState) {
  const container = document.getElementById("metrics-container");
  container.innerHTML = "";

  if (freshnessState === "DELAYED") {
    container.innerHTML += `
      <div style="background: rgba(245,158,11,0.15); border: 1px solid #f59e0b; padding: 6px 10px; border-radius: 6px; font-size: 0.72rem; color: #fbbf24; margin-bottom: 4px;">
        ⏳ Telemetry Ingestion Delayed (15m lag)
      </div>
    `;
  }

  metricsList.forEach(m => {
    const isCrit = m.status === "CRITICAL";
    const statusColor = isCrit ? "#f87171" : "#34d399";
    const bgOpacity = isCrit ? "rgba(239,68,68,0.1)" : "rgba(16,185,129,0.1)";

    const div = document.createElement("div");
    div.className = "stream-item";
    div.style.background = bgOpacity;
    div.innerHTML = `
      <div class="stream-meta">
        <span style="font-weight: 600; color: var(--text-primary);">${m.name}</span>
        <span style="font-weight: 700; color: ${statusColor};">${m.status}</span>
      </div>
      <div style="display: flex; align-items: baseline; justify-content: space-between; margin-top: 4px;">
        <span style="font-size: 1.2rem; font-weight: 700; font-family: var(--font-mono); color: ${statusColor};">
          ${m.current_value} ${m.unit}
        </span>
        <span style="font-size: 0.72rem; color: var(--text-muted);">Baseline: ${m.baseline_value}${m.unit}</span>
      </div>
    `;
    container.appendChild(div);
  });
}

function renderOwnershipStream(ownershipList) {
  const container = document.getElementById("ownership-container");
  if (!ownershipList || ownershipList.length === 0) return;
  const own = ownershipList[0];

  container.innerHTML = `
    <div class="stream-meta">
      <span style="font-weight: 700; color: var(--accent-purple);">${own.team}</span>
      <span>${own.timestamp.substring(11, 16)} UTC</span>
    </div>
    <div style="font-size: 0.8rem; margin-top: 4px;">
      <strong>${own.previous_lead}</strong> ➔ <strong>${own.new_lead}</strong>
    </div>
    <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">
      Shift Rotation Type: ${own.handover_type}
    </div>
  `;
}

function renderHypothesesGraph(hypotheses, evidenceList) {
  const container = document.getElementById("hypotheses-container");
  container.innerHTML = "";

  hypotheses.forEach(hypo => {
    const cardClass = hypo.status.toLowerCase();
    const confPct = Math.round(hypo.confidence_score * 100);

    // Find linked evidence
    const linkedEvid = evidenceList.filter(e => e.hypothesis_id === hypo.id);

    const div = document.createElement("div");
    div.className = `hypo-card ${cardClass}`;

    let evidenceChipsHtml = linkedEvid.map(e => {
      const chipStyle = e.impact === "SUPPORTS" ? "chip-supports" : "chip-refutes";
      const icon = e.impact === "SUPPORTS" ? "✓" : "✗";
      return `
        <span class="evidence-chip ${chipStyle}" onclick="openEvidenceModal('${e.id}')">
          ${icon} ${e.title}
        </span>
      `;
    }).join("");

    div.innerHTML = `
      <div class="hypo-header">
        <div>
          <div class="hypo-title">${hypo.title}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">
            ID: ${hypo.id} | Created by ${hypo.created_by}
          </div>
        </div>
        <span class="freshness-badge ${cardClass === 'confirmed' ? 'badge-fresh' : cardClass === 'disproved' ? 'badge-missing' : 'badge-delayed'}">
          ${hypo.status}
        </span>
      </div>

      <div style="font-size: 0.82rem; color: var(--text-secondary);">${hypo.description}</div>

      <div class="confidence-container">
        <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">Confidence: ${confPct}%</span>
        <div class="confidence-bar-bg">
          <div class="confidence-bar-fill" style="width: ${confPct}%;"></div>
        </div>
      </div>

      <div style="margin-top: 4px;">
        <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 4px;">Drill-Down Evidence:</div>
        <div class="evidence-chip-list">
          ${evidenceChipsHtml || '<span style="font-size: 0.72rem; color: var(--text-muted);">No linked evidence yet</span>'}
        </div>
      </div>
    `;

    container.appendChild(div);
  });
}

function renderActionsQueue(actionsList, changeReviews) {
  const container = document.getElementById("actions-container");
  container.innerHTML = "";

  if (!actionsList || actionsList.length === 0) {
    container.innerHTML = `
      <div style="font-size: 0.8rem; color: var(--color-success); font-weight: 600; padding: 10px; background: rgba(16,185,129,0.1); border-radius: 6px;">
        ✓ All shift action items resolved or executed!
      </div>
    `;
    return;
  }

  actionsList.forEach(act => {
    const isHigh = act.impact_level === "HIGH" || act.impact_level === "CRITICAL";
    const reviewReq = changeReviews.find(r => r.action_id === act.id);
    const isApproved = act.status === "APPROVED";

    const div = document.createElement("div");
    div.className = "action-card";

    div.innerHTML = `
      <div class="action-header">
        <span style="font-weight: 700; font-size: 0.85rem; color: var(--text-primary);">${act.action_name}</span>
        <span class="impact-badge-high">${act.impact_level} IMPACT</span>
      </div>

      <div style="font-size: 0.8rem; color: var(--text-secondary);">${act.description}</div>

      <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border-color);">
        <div style="font-size: 0.72rem; color: var(--text-muted);">
          Status: <strong style="color: ${isApproved ? '#34d399' : '#fbbf24'};">${act.status}</strong>
          ${act.approved_by ? ` (Approved by ${act.approved_by})` : ''}
        </div>

        <div style="display: flex; gap: 6px;">
          ${!isApproved && act.requires_two_person_review ? `
            <button class="btn btn-secondary" style="padding: 3px 8px; font-size: 0.72rem; color: var(--color-warning);" onclick="approveChangeReview('${act.id}')">
              Approve (2-Person Sign)
            </button>
          ` : ''}

          <button class="btn btn-primary" style="padding: 3px 8px; font-size: 0.72rem;" onclick="executeAction('${act.id}')">
            Execute Action
          </button>

          ${act.is_reversible ? `
            <button class="btn btn-danger" style="padding: 3px 8px; font-size: 0.72rem;" onclick="triggerRollback('${act.id}')">
              1-Click Rollback
            </button>
          ` : ''}
        </div>
      </div>
    `;

    container.appendChild(div);
  });
}

function renderAuditTrail(auditList) {
  const container = document.getElementById("audit-trail-container");
  container.innerHTML = "";

  auditList.slice().reverse().forEach(aud => {
    const div = document.createElement("div");
    div.style.cssText = "background: var(--bg-surface-elevated); border: 1px solid var(--border-color); padding: 8px 10px; border-radius: 6px; font-size: 0.75rem;";
    div.innerHTML = `
      <div style="display: flex; justify-content: space-between; color: var(--text-muted);">
        <span style="font-weight: 700; color: var(--accent-cyan);">${aud.action_type}</span>
        <span>${aud.timestamp.substring(11, 19)} UTC</span>
      </div>
      <div style="color: var(--text-primary); margin-top: 2px;">${aud.description}</div>
      <div style="color: var(--text-muted); font-size: 0.7rem; margin-top: 2px;">Actor: ${aud.actor} (${aud.role})</div>
    `;
    container.appendChild(div);
  });
}

function openEvidenceModal(evidenceId) {
  if (!currentWorkspaceData) return;
  const evid = currentWorkspaceData.evidence_list.find(e => e.id === evidenceId);
  if (!evid) return;

  document.getElementById("modal-title").innerText = `Evidence Drill-Down: ${evid.title}`;
  
  const modalContent = document.getElementById("modal-content");
  modalContent.innerHTML = `
    <div style="display: flex; justify-content: space-between; background: var(--bg-surface-elevated); padding: 10px; border-radius: 6px;">
      <div>
        <strong>Source Type:</strong> ${evid.source_type}<br>
        <strong>Source ID:</strong> ${evid.source_id}
      </div>
      <div style="text-align: right;">
        <strong>Impact:</strong> <span style="color: ${evid.impact === 'SUPPORTS' ? '#34d399' : '#f87171'}; font-weight:700;">${evid.impact}</span><br>
        <strong>Added by:</strong> ${evid.added_by} (${evid.added_at.substring(11, 16)} UTC)
      </div>
    </div>

    <div style="background: rgba(0,0,0,0.4); padding: 12px; border-left: 3px solid var(--accent-cyan); font-family: var(--font-mono); font-size: 0.8rem; border-radius: 4px;">
      ${evid.snippet}
    </div>

    <div style="font-size: 0.78rem; color: var(--text-muted);">
      This empirical evidence item directly updates confidence scores in the Hypothesis-Evidence Graph during shift transitions.
    </div>
  `;

  document.getElementById("evidence-modal").classList.add("active");
}

function closeModal() {
  document.getElementById("evidence-modal").classList.remove("active");
}

function openAddHypothesisModal() {
  document.getElementById("add-hypo-modal").classList.add("active");
}

function closeAddHypoModal() {
  document.getElementById("add-hypo-modal").classList.remove("active");
}

async function submitNewHypothesis() {
  const title = document.getElementById("new-hypo-title").value;
  const desc = document.getElementById("new-hypo-desc").value;
  if (!title || !desc) return alert("Please fill in both title and description");

  try {
    const res = await fetch("/api/hypotheses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, description: desc, created_by: "Elena Rostova", confidence_score: 0.5 })
    });
    if (res.ok) {
      closeAddHypoModal();
      fetchWorkspaceData();
    }
  } catch (e) {
    console.error(e);
  }
}

async function approveChangeReview(actionId) {
  try {
    const res = await fetch("/api/change-review/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, approver: "Marcus Vance (Outgoing Lead)" })
    });
    if (res.ok) fetchWorkspaceData();
  } catch (e) { console.error(e); }
}

async function executeAction(actionId) {
  try {
    const res = await fetch("/api/actions/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, executed_by: "Elena Rostova" })
    });
    if (res.ok) fetchWorkspaceData();
  } catch (e) { console.error(e); }
}

async function triggerRollback(actionId) {
  if (!confirm(`Confirm 1-Click Rollback execution for action ${actionId}?`)) return;
  try {
    const res = await fetch("/api/actions/rollback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, actor: "Elena Rostova", rationale: "1-Click Handover Rollback Trigger" })
    });
    if (res.ok) fetchWorkspaceData();
  } catch (e) { console.error(e); }
}

async function toggleSource(sourceName, state) {
  try {
    const res = await fetch("/api/data-sources/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_name: sourceName, state: state })
    });
    if (res.ok) fetchWorkspaceData();
  } catch (e) { console.error(e); }
}

async function submitHandoverSignoff() {
  const outSig = document.getElementById("outgoing-sig-input").value;
  const inSig = document.getElementById("incoming-sig-input").value;
  try {
    const res = await fetch("/api/handover/signoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outgoing_lead_signature: outSig, incoming_lead_signature: inSig })
    });
    if (res.ok) fetchWorkspaceData();
  } catch (e) { console.error(e); }
}

async function runBenchmark() {
  try {
    const res = await fetch("/api/benchmark?trials=100");
    if (!res.ok) return;
    const bench = await res.json();

    document.getElementById("delay-baseline-val").innerText = `${bench.baseline_handover_delay_minutes.toFixed(1)} min`;
    document.getElementById("delay-solution-val").innerText = `${bench.solution_handover_delay_minutes.toFixed(1)} min`;

    const pctSolution = Math.min(100, Math.max(10, (bench.solution_handover_delay_minutes / bench.baseline_handover_delay_minutes) * 100));
    document.getElementById("bar-solution").style.width = `${pctSolution}%`;

    document.getElementById("bench-reduction-pct").innerText = `${bench.percentage_reduction}% (${bench.delay_reduction_minutes} min saved)`;
    document.getElementById("bench-mttr-pct").innerText = `${bench.mttr_reduction_percent}% (${bench.baseline_mttr_minutes}m ➔ ${bench.solution_mttr_minutes}m)`;
    document.getElementById("bench-rework-val").innerText = `${bench.baseline_rework_rate_percent}% ➔ ${bench.solution_rework_rate_percent}%`;
    document.getElementById("bench-error-analysis").innerText = bench.error_analysis;
  } catch (e) {
    console.error(e);
  }
}

async function resetScenario() {
  try {
    const res = await fetch("/api/reset", { method: "POST" });
    if (res.ok) {
      fetchWorkspaceData();
      runBenchmark();
    }
  } catch (e) { console.error(e); }
}

function switchRole(role) {
  activeRole = role;
  fetchWorkspaceData();
}

function switchTab(evt, tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

  if (evt && evt.currentTarget) {
    evt.currentTarget.classList.add("active");
  }
  const tabContent = document.getElementById(tabId);
  if (tabContent) {
    tabContent.classList.add("active");
  }
}
