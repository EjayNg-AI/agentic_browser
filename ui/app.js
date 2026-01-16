const api = {
  runs: "/ui/api/runs",
  runDetail: (runId) => `/ui/api/runs/${runId}`,
};

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function renderEmpty(container, message) {
  container.innerHTML = "";
  const empty = el("div", "empty");
  empty.textContent = message;
  container.appendChild(empty);
}

async function loadRuns() {
  const container = document.getElementById("runs-list");
  if (!container) return;
  try {
    const resp = await fetch(api.runs);
    const data = await resp.json();
    const runs = data.runs || [];
    if (!runs.length) {
      renderEmpty(container, "No runs yet.");
      return;
    }
    container.innerHTML = "";
    runs.forEach((run) => {
      const card = el("a", "run-card");
      card.href = `/runs/${run.run_id}`;
      const title = el("div", "run-title");
      title.textContent = run.run_id;
      const status = el("div", "run-status");
      status.textContent = run.status || "unknown";
      const meta = el("div", "run-meta");
      meta.textContent = `session ${run.session_id || "-"}`;
      card.append(title, status, meta);
      container.appendChild(card);
    });
  } catch (err) {
    renderEmpty(container, "Failed to load runs.");
  }
}

function renderMetadata(container, metadata) {
  container.innerHTML = "";
  const items = [
    ["Run", metadata.run_id],
    ["Status", metadata.status],
    ["Session", metadata.session_id],
    ["Started", metadata.started_at],
    ["Finished", metadata.finished_at],
  ];
  items.forEach(([label, value]) => {
    const row = el("div", "meta-row");
    const key = el("div", "meta-key");
    key.textContent = label;
    const val = el("div", "meta-val");
    val.textContent = value || "-";
    row.append(key, val);
    container.appendChild(row);
  });
}

function renderSteps(container, steps, runId) {
  container.innerHTML = "";
  if (!steps.length) {
    renderEmpty(container, "No steps recorded.");
    return;
  }
  steps.forEach((record) => {
    const card = el("div", "step-card");
    const header = el("div", "step-header");
    header.textContent = `#${record.index} ${record.step.type} (${record.status})`;
    const details = el("div", "step-details");
    details.textContent = JSON.stringify(record.result, null, 2);
    if (record.result && record.result.screenshot) {
      const link = el("a", "artifact-link");
      link.href = `/runs/${runId}/${record.result.screenshot}`;
      link.textContent = "Screenshot";
      link.target = "_blank";
      card.appendChild(link);
    }
    card.append(header, details);
    container.appendChild(card);
  });
}

function renderNotes(container, notes, runId) {
  container.innerHTML = "";
  if (!notes.length) {
    renderEmpty(container, "No notes yet.");
    return;
  }
  notes.forEach((note) => {
    const card = el("div", "note-card");
    const header = el("div", "note-header");
    header.textContent = `${note.note_kind || note.type}`;
    const meta = el("div", "note-meta");
    meta.textContent = `${note.title || "Untitled"} - ${note.url || ""}`;
    const body = el("pre", "note-body");
    body.textContent = JSON.stringify(note.content || {}, null, 2);
    card.append(header, meta, body);
    if (note.evidence) {
      const evidence = el("div", "note-evidence");
      if (note.evidence.screenshot) {
        const shot = el("a", "artifact-link");
        shot.href = `/runs/${runId}/${note.evidence.screenshot}`;
        shot.textContent = "Screenshot";
        shot.target = "_blank";
        evidence.appendChild(shot);
      }
      if (note.evidence.html) {
        const html = el("a", "artifact-link");
        html.href = `/runs/${runId}/${note.evidence.html}`;
        html.textContent = "HTML snapshot";
        html.target = "_blank";
        evidence.appendChild(html);
      }
      card.appendChild(evidence);
    }
    container.appendChild(card);
  });
}

async function loadRun(runId) {
  const metaEl = document.getElementById("run-meta");
  const stepsEl = document.getElementById("run-steps");
  const notesEl = document.getElementById("run-notes");
  const subtitle = document.getElementById("run-subtitle");
  const assistSection = document.getElementById("manual-assist");
  const assistMessage = document.getElementById("assist-message");
  const assistEvidence = document.getElementById("assist-evidence");
  const assistButton = document.getElementById("assist-resume");
  try {
    const resp = await fetch(api.runDetail(runId));
    const data = await resp.json();
    if (subtitle) subtitle.textContent = runId;
    const metadata = data.metadata || {};
    renderMetadata(metaEl, metadata);
    renderSteps(stepsEl, data.steps || [], runId);
    renderNotes(notesEl, data.notes || [], runId);
    if (assistSection) {
      const manual = data.manual_assist;
      if (metadata.status === "NEEDS_MANUAL_ASSIST") {
        assistSection.classList.remove("hidden");
        if (assistMessage) {
          assistMessage.textContent =
            (manual && manual.message) || "Manual assist is required.";
        }
        if (assistEvidence) {
          assistEvidence.innerHTML = "";
          if (manual && manual.screenshot) {
            const img = el("img", "assist-shot");
            img.src = `/runs/${runId}/${manual.screenshot}`;
            img.alt = "Manual assist screenshot";
            assistEvidence.appendChild(img);
          }
        }
        if (assistButton) {
          assistButton.onclick = async () => {
            await fetch("/v1/resume", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ session_id: metadata.session_id }),
            });
          };
        }
      } else {
        assistSection.classList.add("hidden");
      }
    }
  } catch (err) {
    if (metaEl) renderEmpty(metaEl, "Failed to load run.");
  }
}

function getRunIdFromPath() {
  const match = window.location.pathname.match(/^\/runs\/([^/]+)$/);
  return match ? match[1] : null;
}

loadRuns();

const runId = getRunIdFromPath();
if (runId) {
  loadRun(runId);
  setInterval(() => loadRun(runId), 2000);
}
