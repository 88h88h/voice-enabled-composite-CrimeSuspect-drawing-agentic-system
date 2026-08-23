const API_BASE = "http://localhost:8000";

const FIELD_LABELS = {
  face_shape: "face shape",
  eyes_shape: "eye shape",
  eyes_spacing: "eye spacing",
  eyebrows_thickness: "eyebrow thickness",
  nose_size: "nose size",
  nose_shape: "nose shape",
  mouth_width: "mouth width",
  jaw_shape: "jaw shape",
  hair_length: "hair length",
  hair_texture: "hair texture",
  hair_color: "hair color",
  facial_hair: "facial hair",
};

let currentCaseId = null;
let pollTimer = null;
// witnessState[i] = { sessionId, agoraClient, joined }
const witnessState = [{}, {}];

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${options.method || "GET"} ${path} failed: ${res.status} ${body}`);
  }
  return res.json();
}

async function checkBackend() {
  const el = document.getElementById("backend-status");
  try {
    await api("/health");
    el.textContent = "connected";
    el.style.color = "green";
  } catch (e) {
    el.textContent = "not reachable (is the server running on :8000?)";
    el.style.color = "red";
  }
}

document.getElementById("create-case-btn").addEventListener("click", async () => {
  const incident_location = document.getElementById("incident-location").value.trim();
  const incident_description = document.getElementById("incident-description").value.trim();
  if (!incident_location) {
    alert("Incident location is required (used for jurisdiction lookup).");
    return;
  }
  const caseObj = await api("/cases", {
    method: "POST",
    body: JSON.stringify({ incident_location, incident_description }),
  });
  currentCaseId = caseObj.id;
  document.getElementById("case-setup").style.display = "none";
  document.getElementById("case-panel").style.display = "block";
  document.getElementById("case-ref").textContent = `${caseObj.id} (${caseObj.reference_code})`;
  startPolling();
});

document.querySelectorAll(".start-session-btn").forEach((btn, idx) => {
  btn.addEventListener("click", async () => {
    const card = btn.closest(".witness-card");
    const label = card.querySelector("h3").textContent;
    const session = await api(`/cases/${currentCaseId}/sessions`, {
      method: "POST",
      body: JSON.stringify({ witness_label: label }),
    });
    witnessState[idx].sessionId = session.id;
    btn.style.display = "none";
    card.querySelector(".join-voice-btn").style.display = "inline-block";
  });
});

document.querySelectorAll(".join-voice-btn").forEach((btn, idx) => {
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "connecting...";
    try {
      const { app_id, channel_name, frontend_uid, frontend_token } = await api("/agora/agent/start", {
        method: "POST",
        body: JSON.stringify({ case_id: currentCaseId, session_id: witnessState[idx].sessionId }),
      });

      const client = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
      await client.join(app_id, channel_name, frontend_token, frontend_uid);
      const micTrack = await AgoraRTC.createMicrophoneAudioTrack();
      await client.publish([micTrack]);

      witnessState[idx].agoraClient = client;
      witnessState[idx].joined = true;
      btn.textContent = "on call";
      btn.classList.add("secondary");
    } catch (err) {
      console.error(err);
      btn.disabled = false;
      btn.textContent = "Join voice (mic)";
      alert(
        "Could not join the voice channel. This requires real Agora credentials configured in the backend's .env (see Phase 0 checklist) -- expected to fail with placeholder keys.\n\n" +
          err.message
      );
    }
  });
});

document.getElementById("signoff-btn").addEventListener("click", async () => {
  const signed_off_by = document.getElementById("signoff-name").value.trim() || "Unnamed caseworker";
  try {
    await api(`/cases/${currentCaseId}/signoff`, {
      method: "POST",
      body: JSON.stringify({ signed_off_by }),
    });
    refreshState();
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("escalate-btn").addEventListener("click", async () => {
  const reason = document.getElementById("escalate-reason").value.trim() || "manually escalated from UI";
  try {
    await api(`/cases/${currentCaseId}/escalate`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    refreshState();
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("reconcile-btn").addEventListener("click", async () => {
  try {
    const result = await api(`/cases/${currentCaseId}/reconcile`, { method: "POST" });
    if (result.conflicts.length) {
      alert(`Reconciliation found ${result.conflicts.length} conflicting field(s) -- case escalated for human review.`);
    } else {
      alert("Both witnesses agree on all shared features. No conflicts.");
    }
    refreshState();
  } catch (e) {
    alert(e.message);
  }
});

function renderFeatureList(ul, params) {
  ul.innerHTML = "";
  for (const [field, label] of Object.entries(FIELD_LABELS)) {
    const value = params[field];
    if (value == null) continue;
    const verbatim = params[`${field}_verbatim`] || "";
    const li = document.createElement("li");
    li.innerHTML = `<span class="interp">${label}: ${value}</span><br/><span class="verbatim">"${verbatim}"</span>`;
    ul.appendChild(li);
  }
  if (params.distinguishing_marks && params.distinguishing_marks.length) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="interp">marks: ${params.distinguishing_marks.join(", ")}</span>`;
    ul.appendChild(li);
  }
}

async function refreshState() {
  if (!currentCaseId) return;
  const state = await api(`/cases/${currentCaseId}/state`);

  document.getElementById("case-status").textContent = state.case.status;
  document.getElementById("case-jurisdiction").textContent =
    `${state.case.jurisdiction_name} (${state.case.jurisdiction_contact})`;

  const escBox = document.getElementById("escalation-banners");
  escBox.innerHTML = state.escalations
    .map((e) => `<div class="banner escalation">Escalated (${e.source}): ${e.reason}</div>`)
    .join("");

  const conflictBox = document.getElementById("conflict-banners");
  conflictBox.innerHTML = state.conflicts
    .map(
      (c) =>
        `<div class="banner conflict">Conflict on "${c.field_name}": witness A said "${c.witness_a_value}", witness B said "${c.witness_b_value}" -- needs human review</div>`
    )
    .join("");

  document.querySelectorAll(".witness-card").forEach((card, idx) => {
    const w = state.witnesses.find((w) => w.session.id === witnessState[idx].sessionId);
    if (!w) return;
    renderFeatureList(card.querySelector(".feature-list"), w.parameters);

    const img = card.querySelector(".sketch-img");
    const watermark = card.querySelector(".draft-watermark");
    if (w.latest_sketch_status === "READY" && w.latest_sketch_url) {
      img.src = `${w.latest_sketch_url}?_=${Date.now()}`; // cache-bust so edits show immediately
      img.style.display = "block";
      const isFinal = state.case.status === "CONFIRMED";
      watermark.style.display = isFinal ? "none" : "flex";
    } else if (w.latest_sketch_status === "GENERATION_FAILED") {
      img.style.display = "none";
      watermark.style.display = "none";
    }
  });
}

function startPolling() {
  refreshState();
  pollTimer = setInterval(refreshState, 2000);
}

checkBackend();
