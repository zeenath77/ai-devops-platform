const API_URL = "https://9q8vmkht4f.execute-api.us-east-1.amazonaws.com";
const CODE_BUCKET = "ai-devops-generated-code-367273783701";

let allProjects = [];
let statusChart = null;

function badge(status) {
  const safe = String(status || "unknown").replace(/[^a-z0-9_-]/gi, "_");
  return `<span class="status-badge ${safe}">${escapeText(status || "unknown")}</span>`;
}

function escapeText(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[ch]);
}

function timeAgo(ts) {
  const diff = Math.floor(Date.now() / 1000) - (ts || 0);

  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;

  return `${Math.floor(diff / 86400)}d ago`;
}

function showToast(message, type = "") {
  const root = document.getElementById("toastRoot");
  const el = document.createElement("div");

  el.className = `toast ${type}`;
  el.textContent = message;

  root.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

function animateCount(el, target, isPercent) {
  if (!el) return;

  const start = parseFloat(el.dataset.target) || 0;
  const duration = 600;
  const startTime = performance.now();

  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const value = start + (target - start) * progress;

    el.textContent = isPercent
      ? `${value.toFixed(1)}%`
      : Math.round(value);

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      el.dataset.target = target;
    }
  }

  requestAnimationFrame(step);
}

// ---------------- NAVIGATION ----------------

function switchTab(tabId) {
  const target = document.getElementById(`tab-${tabId}`);
  if (!target) return;

  document.querySelectorAll(".tab").forEach(t => {
    t.classList.add("hidden");
  });

  target.classList.remove("hidden");

  document.querySelectorAll(".rail-item").forEach(button => {
    button.classList.toggle(
      "active",
      button.dataset.tab === tabId
    );
  });

  if (tabId === "monitoring") loadMonitoring();
  if (tabId === "quality") updateQualitySummary();
}

document.querySelectorAll(".rail-item").forEach(btn => {
  btn.addEventListener("click", () => {
    switchTab(btn.dataset.tab);
  });
});

// ---------------- API STATUS ----------------

async function checkApi() {
  const dot = document.getElementById("apiStatusDot");
  const text = document.getElementById("apiStatusText");

  try {
    const res = await fetch(`${API_URL}/metrics`);

    if (res.ok) {
      dot.className = "status-dot ok";
      text.textContent = "API connected";
    } else {
      dot.className = "status-dot bad";
      text.textContent = `API error ${res.status}`;
    }
  } catch (e) {
    dot.className = "status-dot bad";
    text.textContent = "API unreachable";
  }
}

// ---------------- METRICS ----------------

async function loadMetrics() {
  try {
    const res = await fetch(`${API_URL}/metrics`);

    if (!res.ok) {
      throw new Error("Metrics request failed");
    }

    const data = await res.json();

    animateCount(
      document.getElementById("statTotal"),
      data.total_runs ?? 0,
      false
    );

    animateCount(
      document.getElementById("statRate"),
      data.success_rate ?? 0,
      true
    );

    animateCount(
      document.getElementById("statFailed"),
      data.failed ?? 0,
      false
    );

    const qualityRuns = document.getElementById("qualityRunCount");

    if (qualityRuns) {
      qualityRuns.textContent = data.total_runs ?? 0;
      document.getElementById("qualityFailedCount").textContent =
        data.failed ?? 0;

      document.getElementById("qualityAnalyzedCount").textContent =
        data.analyzed ?? "—";
    }

    document.getElementById("monitorTotal").textContent =
      data.total_runs ?? 0;

    document.getElementById("monitorSuccess").textContent =
      data.succeeded ?? 0;

    document.getElementById("monitorFailed").textContent =
      data.failed ?? 0;

    document.getElementById("monitorRate").textContent =
      `${data.success_rate ?? 0}%`;

  } catch (e) {
    console.error("Could not load metrics:", e);
  }
}

// ---------------- STATUS CHART ----------------

function renderStatusChart() {
  const counts = {};

  allProjects.forEach(p => {
    const s = p.status || "unknown";
    counts[s] = (counts[s] || 0) + 1;
  });

  const labels = Object.keys(counts);
  const values = Object.values(counts);

  const colors = {
    generated: "#34D399",
    failed: "#FB7185",
    generating: "#3B82F6",
    modified: "#7C3AED"
  };

  const ctx = document.getElementById("statusChart");

  if (!ctx || !window.Chart) return;

  const data = {
    labels,
    datasets: [{
      data: values,
      backgroundColor: labels.map(
        label => colors[label] || "#9691C4"
      ),
      borderWidth: 0
    }]
  };

  if (statusChart) {
    statusChart.data = data;
    statusChart.update();
  } else {
    statusChart = new Chart(ctx, {
      type: "doughnut",
      data,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#9691C4",
              font: {
                family: "Inter",
                size: 11
              },
              padding: 14
            }
          }
        }
      }
    });
  }
}

// ---------------- ACTIVITY FEED ----------------

function renderActivityFeed() {
  const feed = document.getElementById("activityFeed");

  const recent = [...allProjects]
    .sort((a, b) => (b.created_at || 0) - (a.created_at || 0))
    .slice(0, 6);

  feed.innerHTML = recent.map(p => `
    <div class="activity-item">
      <span class="activity-dot ${escapeText(p.status)}"></span>
      <span>
        <span class="activity-text">
          ${escapeText(p.project_id)} — ${escapeText(p.status)}
        </span>
        <span class="activity-time">${timeAgo(p.created_at)}</span>
      </span>
    </div>
  `).join("") || `<p class="hint">No activity yet.</p>`;
}

// ---------------- PROJECTS ----------------

async function loadProjects() {
  try {
    const res = await fetch(`${API_URL}/projects`);

    if (!res.ok) {
      throw new Error("Projects request failed");
    }

    const data = await res.json();

    allProjects = (data.projects || [])
      .sort((a, b) => (b.created_at || 0) - (a.created_at || 0));

    animateCount(
      document.getElementById("statProjects"),
      allProjects.length,
      false
    );

    renderStatusChart();
    renderActivityFeed();

    const overviewBody = document.querySelector("#overviewTable tbody");
    overviewBody.innerHTML = "";

    allProjects.slice(0, 8).forEach(p => {
      const row = document.createElement("tr");

      row.innerHTML = `
        <td>${escapeText(p.project_id)}</td>
        <td>${escapeText(p.stack || "–")}</td>
        <td>${badge(p.status)}</td>
        <td>${new Date((p.created_at || 0) * 1000).toLocaleString()}</td>
      `;

      overviewBody.appendChild(row);
    });

    renderProjectsTable(
      document.getElementById("projectSearch").value
    );

  } catch (e) {
    console.error("Could not load projects:", e);
  }
}

function renderProjectsTable(filterText) {
  const term = (filterText || "").toLowerCase();

  const filtered = allProjects.filter(p =>
    !term ||
    String(p.project_id || "").toLowerCase().includes(term) ||
    String(p.stack || "").toLowerCase().includes(term)
  );

  const projectsBody = document.querySelector("#projectsTable tbody");
  projectsBody.innerHTML = "";

  filtered.forEach(p => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${escapeText(p.project_id)}</td>
      <td>${escapeText(p.stack || "–")}</td>
      <td>${badge(p.status)}</td>
      <td>${new Date((p.created_at || 0) * 1000).toLocaleString()}</td>
      <td>
        <button class="row-select" data-id="${escapeText(p.project_id)}">
          Open
        </button>
      </td>
    `;

    projectsBody.appendChild(row);
  });

  document.querySelectorAll(".row-select").forEach(btn => {
    btn.addEventListener("click", () => {
      openDrawer(btn.dataset.id);
    });
  });
}

document.getElementById("projectSearch").addEventListener("input", e => {
  renderProjectsTable(e.target.value);
});

// ---------------- PROJECT DRAWER ----------------

async function openDrawer(projectId) {
  const p = allProjects.find(x => x.project_id === projectId);
  if (!p) return;

  document.getElementById("drawerTitle").textContent = projectId;
  document.getElementById("drawerStack").textContent = p.stack || "–";
  document.getElementById("drawerDescription").textContent =
    p.description || "–";

  document.getElementById("drawerFiles").textContent =
    (p.file_paths || []).join(", ") || "–";

  document.getElementById("drawerDownloadCmd").textContent =
    `aws s3 sync s3://${CODE_BUCKET}/${projectId}/ ./generated-project`;

  document.getElementById("drawerPipelineCmd").textContent =
    `GitHub repo → Actions → AI-DevOps-Pipeline → Run workflow → project_id: ${projectId}`;

  document.getElementById("deploymentsProjectId").value = projectId;
  document.getElementById("runsProjectId").value = projectId;
  document.getElementById("qualityProjectId").value = projectId;

  let deployed = false;
  let reviewed = false;

  try {
    const depRes = await fetch(
      `${API_URL}/deployments/${encodeURIComponent(projectId)}`
    );

    const depData = await depRes.json();

    deployed = (depData.deployments || []).some(d =>
      d.status === "deployed" || d.status === "rolled_back"
    );
  } catch (e) {}

  try {
    const runRes = await fetch(
      `${API_URL}/pipeline-runs/${encodeURIComponent(projectId)}`
    );

    const runData = await runRes.json();
    reviewed = (runData.runs || []).length > 0;
  } catch (e) {}

  const generated =
    ["generated", "modified"].includes(p.status) || deployed;

  const failed = p.status === "failed";

  const steps = [
    { label: "Generated", done: generated, failed },
    { label: "Reviewed & scanned", done: reviewed },
    { label: "Deployed", done: deployed }
  ];

  document.getElementById("drawerStepper").innerHTML = steps.map(s => `
    <div class="step ${s.failed ? "failed" : s.done ? "done" : ""}">
      <span class="step-dot">
        ${s.failed ? "✕" : s.done ? "✓" : ""}
      </span>
      <span class="step-label">${s.label}</span>
    </div>
  `).join("");

  document.getElementById("drawerOverlay").classList.remove("hidden");
  document.getElementById("projectDrawer").classList.add("open");
}

function closeDrawer() {
  document.getElementById("drawerOverlay").classList.add("hidden");
  document.getElementById("projectDrawer").classList.remove("open");
}

document.getElementById("drawerClose").addEventListener("click", closeDrawer);
document.getElementById("drawerOverlay").addEventListener("click", closeDrawer);

// ---------------- PROJECT GENERATION / POLLING ----------------

async function pollProject(projectId, resultEl, btn, btnLabel, progressEl) {
  const maxAttempts = 30;

  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 3000));

    try {
      const res = await fetch(
        `${API_URL}/projects/${encodeURIComponent(projectId)}`
      );

      const data = await res.json();

      if (data.status === "generated" || data.status === "modified") {
        resultEl.textContent = JSON.stringify(data, null, 2);
        resultEl.classList.remove("empty");

        progressEl.classList.add("hidden");
        loadProjects();

        showToast(`${projectId} generated successfully`, "success");

        btn.disabled = false;
        btn.textContent = btnLabel;
        return;
      }

      if (data.status === "failed") {
        resultEl.textContent =
          "Failed: " + (data.error_message || "unknown error");

        resultEl.classList.remove("empty");
        progressEl.classList.add("hidden");

        loadProjects();
        showToast(`${projectId} failed`, "error");

        btn.disabled = false;
        btn.textContent = btnLabel;
        return;
      }

      resultEl.textContent = `Still working... (${(i + 1) * 3}s)`;
      resultEl.classList.remove("empty");

    } catch (e) {
      resultEl.textContent = "Error while polling: " + e.message;
      resultEl.classList.remove("empty");
    }
  }

  resultEl.textContent = "Timed out. Check the Projects tab in a moment.";

  progressEl.classList.add("hidden");
  btn.disabled = false;
  btn.textContent = btnLabel;
}

async function generateProject() {
  const prompt = document.getElementById("promptInput").value.trim();
  const stack = document.getElementById("stackSelect")?.value || "";

  if (!prompt) {
    return showToast("Describe the project you want to generate.", "error");
  }

  const btn = document.getElementById("generateBtn");
  const resultEl = document.getElementById("generateResult");
  const progressEl = document.getElementById("generateProgress");

  btn.disabled = true;
  btn.textContent = "Generating...";
  progressEl.classList.remove("hidden");

  try {
    const res = await fetch(`${API_URL}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: `${prompt}\n\nPreferred technology stack: ${stack}`
      })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    if (!data.project_id) {
      resultEl.textContent = JSON.stringify(data, null, 2);
      resultEl.classList.remove("empty");

      progressEl.classList.add("hidden");
      btn.disabled = false;
      btn.textContent = "Generate project";
      return;
    }

    resultEl.textContent = `Started. Project ID: ${data.project_id}`;
    resultEl.classList.remove("empty");

    showToast(`Started generating ${data.project_id}`);
    loadProjects();

    pollProject(
      data.project_id,
      resultEl,
      btn,
      "Generate project",
      progressEl
    );

  } catch (e) {
    resultEl.textContent = "Error: " + (e.message || e);
    resultEl.classList.remove("empty");

    progressEl.classList.add("hidden");
    btn.disabled = false;
    btn.textContent = "Generate project";
  }
}

// ---------------- MODIFY PROJECT ----------------

async function modifyProject() {
  const projectId = document.getElementById("modifyProjectId").value.trim();
  const instruction = document.getElementById("modifyInstruction").value.trim();

  if (!projectId || !instruction) {
    return showToast(
      "Enter a project ID and modification instruction.",
      "error"
    );
  }

  const btn = document.getElementById("modifyBtn");
  const resultEl = document.getElementById("modifyResult");

  btn.disabled = true;
  btn.textContent = "Modifying...";

  try {
    const res = await fetch(
      `${API_URL}/projects/${encodeURIComponent(projectId)}/modify`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction })
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    resultEl.textContent = JSON.stringify(data, null, 2);
    resultEl.classList.remove("empty");

    showToast(`Modification submitted for ${projectId}`, "success");
    loadProjects();

  } catch (e) {
    resultEl.textContent = "Error: " + e.message;
    resultEl.classList.remove("empty");

    showToast(`Modify failed: ${e.message}`, "error");

  } finally {
    btn.disabled = false;
    btn.textContent = "Modify";
  }
}

// ---------------- DEPLOYMENTS ----------------

async function loadDeployments() {
  const projectId = document.getElementById("deploymentsProjectId").value.trim();

  if (!projectId) {
    return showToast("Enter a project ID first.", "error");
  }

  const body = document.querySelector("#deploymentsTable tbody");

  body.innerHTML = `
    <tr>
      <td colspan="4" class="hint">Loading deployments…</td>
    </tr>
  `;

  try {
    const res = await fetch(
      `${API_URL}/deployments/${encodeURIComponent(projectId)}`
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    body.innerHTML = (data.deployments || []).map(d => `
      <tr>
        <td>${escapeText(d.deployment_id)}</td>
        <td>${badge(d.status)}</td>
        <td>${escapeText(d.revision ?? "–")}</td>
        <td>
          ${d.deployed_at
            ? new Date(d.deployed_at * 1000).toLocaleString()
            : "–"}
        </td>
      </tr>
    `).join("") || `
      <tr>
        <td colspan="4" class="hint">No deployments found.</td>
      </tr>
    `;

  } catch (e) {
    body.innerHTML = `
      <tr>
        <td colspan="4" class="hint">
          Could not load deployments: ${escapeText(e.message)}
        </td>
      </tr>
    `;
  }
}

async function rollback() {
  const projectId = document.getElementById("deploymentsProjectId").value.trim();

  if (!projectId) {
    return showToast("Enter a project ID first.", "error");
  }

  if (!confirm(`Roll back project ${projectId}?`)) return;

  const btn = document.getElementById("rollbackBtn");
  btn.disabled = true;

  try {
    const res = await fetch(
      `${API_URL}/projects/${encodeURIComponent(projectId)}/rollback`,
      {
        method: "POST"
      }
    );

    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    showToast(`Rollback submitted for ${projectId}`, "success");
    loadDeployments();

  } catch (e) {
    showToast(`Rollback failed: ${e.message}`, "error");

  } finally {
    btn.disabled = false;
  }
}

// ---------------- PIPELINE RUNS ----------------

async function loadRuns() {
  const projectId = document.getElementById("runsProjectId").value.trim();

  if (!projectId) {
    return showToast("Enter a project ID first.", "error");
  }

  const body = document.querySelector("#runsTable tbody");

  body.innerHTML = `
    <tr>
      <td colspan="4" class="hint">Loading pipeline runs…</td>
    </tr>
  `;

  try {
    const res = await fetch(
      `${API_URL}/pipeline-runs/${encodeURIComponent(projectId)}`
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    body.innerHTML = (data.runs || []).map(r => {
      const analysis = r.failure_analysis || {};

      return `
        <tr>
          <td>${escapeText(r.run_id || "–")}</td>
          <td>${badge(r.status)}</td>
          <td>${escapeText(analysis.root_cause || "–")}</td>
          <td>${escapeText(analysis.suggested_fix || "–")}</td>
        </tr>
      `;
    }).join("") || `
      <tr>
        <td colspan="4" class="hint">No pipeline runs found.</td>
      </tr>
    `;

  } catch (e) {
    body.innerHTML = `
      <tr>
        <td colspan="4" class="hint">
          Could not load pipeline runs: ${escapeText(e.message)}
        </td>
      </tr>
    `;
  }
}

// ---------------- MONITORING ----------------

async function loadMonitoring() {
  const feed = document.getElementById("monitoringFeed");

  try {
    const [metricsRes, projectsRes] = await Promise.all([
      fetch(`${API_URL}/metrics`),
      fetch(`${API_URL}/projects`)
    ]);

    if (!metricsRes.ok || !projectsRes.ok) {
      throw new Error("Metrics endpoint unavailable");
    }

    const metrics = await metricsRes.json();
    const projectData = await projectsRes.json();
    const projects = projectData.projects || [];

    document.getElementById("monitorTotal").textContent =
      metrics.total_runs ?? 0;

    document.getElementById("monitorSuccess").textContent =
      metrics.succeeded ?? 0;

    document.getElementById("monitorFailed").textContent =
      metrics.failed ?? 0;

    document.getElementById("monitorRate").textContent =
      `${metrics.success_rate ?? 0}%`;

    feed.innerHTML = [...projects]
      .sort((a, b) => (b.created_at || 0) - (a.created_at || 0))
      .slice(0, 8)
      .map(p => `
        <div class="activity-item">
          <span class="activity-dot ${escapeText(p.status || "pending")}"></span>
          <span>
            <span class="activity-text">
              ${escapeText(p.project_id)} · ${escapeText(p.status || "unknown")}
            </span>
            <span class="activity-time">
              ${p.created_at
                ? new Date(p.created_at * 1000).toLocaleString()
                : "Timestamp unavailable"}
            </span>
          </span>
        </div>
      `).join("") || `
        <p class="hint">No project activity recorded yet.</p>
      `;

  } catch (err) {
    feed.innerHTML = `
      <p class="hint">
        Could not load monitoring data: ${escapeText(err.message || err)}
      </p>
    `;
  }
}

// ---------------- QUALITY & SECURITY ----------------

async function loadQualityRuns() {
  const projectId = document.getElementById("qualityProjectId").value.trim();

  if (!projectId) {
    return showToast("Enter a project ID first.", "error");
  }

  const body = document.querySelector("#qualityTable tbody");

  body.innerHTML = `
    <tr>
      <td colspan="4" class="hint">Loading pipeline records…</td>
    </tr>
  `;

  try {
    const res = await fetch(
      `${API_URL}/pipeline-runs/${encodeURIComponent(projectId)}`
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }

    const runs = data.runs || [];

    body.innerHTML = runs.map(r => {
      const a = r.failure_analysis || {};

      return `
        <tr>
          <td>${escapeText(r.run_id || "–")}</td>
          <td>${badge(r.status)}</td>
          <td>${escapeText(a.root_cause || "No root-cause analysis recorded")}</td>
          <td>${escapeText(a.suggested_fix || "No suggested fix recorded")}</td>
        </tr>
      `;
    }).join("") || `
      <tr>
        <td colspan="4" class="hint">
          No pipeline runs found for this project.
        </td>
      </tr>
    `;

    showToast(`Loaded ${runs.length} pipeline run(s).`, "success");

  } catch (err) {
    body.innerHTML = `
      <tr>
        <td colspan="4" class="hint">
          Could not load runs: ${escapeText(err.message || err)}
        </td>
      </tr>
    `;
  }
}

function updateQualitySummary() {
  document.getElementById("qualityProjectCount").textContent =
    allProjects.length;
}

// ---------------- EVENT LISTENERS ----------------

document.getElementById("generateBtn").addEventListener("click", generateProject);
document.getElementById("modifyBtn").addEventListener("click", modifyProject);
document.getElementById("loadDeploymentsBtn").addEventListener("click", loadDeployments);
document.getElementById("rollbackBtn").addEventListener("click", rollback);
document.getElementById("loadRunsBtn").addEventListener("click", loadRuns);
document.getElementById("loadQualityBtn").addEventListener("click", loadQualityRuns);
document.getElementById("refreshMonitoringBtn").addEventListener("click", loadMonitoring);

document.querySelectorAll("[data-prompt]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.getElementById("promptInput").value = btn.dataset.prompt;
  });
});

document.querySelectorAll("[data-modify]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.getElementById("modifyInstruction").value = btn.dataset.modify;
  });
});

// ---------------- VISUAL UX POLISH ----------------

(function initVisualPolish() {
  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  // Pointer-following glow on cards
  if (
    !reducedMotion &&
    window.matchMedia("(pointer: fine)").matches
  ) {
    document.querySelectorAll(".stat-card, .panel").forEach(card => {
      card.addEventListener("pointermove", event => {
        const rect = card.getBoundingClientRect();

        const x = ((event.clientX - rect.left) / rect.width) * 100;
        const y = ((event.clientY - rect.top) / rect.height) * 100;

        card.style.backgroundImage = `
          radial-gradient(
            circle at ${x}% ${y}%,
            rgba(126, 104, 255, .075),
            transparent 42%
          )
        `;
      });

      card.addEventListener("pointerleave", () => {
        card.style.backgroundImage = "";
      });
    });
  }
})();

// ---------------- INITIALIZATION ----------------

checkApi();
loadMetrics();
loadProjects();

setInterval(checkApi, 20000);
setInterval(loadMetrics, 15000);
setInterval(loadProjects, 15000);