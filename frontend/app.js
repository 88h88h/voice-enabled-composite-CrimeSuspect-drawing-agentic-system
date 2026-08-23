const API_BASE = "http://localhost:8000";

const FIELD_LABELS = {
  face_shape: "face shape",
  eyes_shape: "eye shape",
  eyes_spacing: "eye spacing",
  eyebrows_thickness: "eyebrows",
  nose_size: "nose size",
  nose_shape: "nose shape",
  mouth_width: "mouth",
  jaw_shape: "jaw",
  hair_length: "hair length",
  hair_texture: "hair texture",
  hair_color: "hair color",
  facial_hair: "facial hair",
};

let currentCaseId = null;
let activeWitnessTab = 0;
// witnessState[i] = { sessionId, label, agoraClient, micTrack, levelInterval }
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
  const pill = document.getElementById("backend-status");
  const text = document.getElementById("backend-status-text");
  try {
    await api("/health");
    pill.classList.add("ok");
    text.textContent = "connected";
  } catch (e) {
    pill.classList.add("bad");
    text.textContent = "backend not reachable on :8000";
  }
}

// ---------- Voice join (shared by witness 1 and witness 2) ----------

async function joinWitnessVoice(idx) {
  const { app_id, channel_name, frontend_uid, frontend_token } = await api("/agora/agent/start", {
    method: "POST",
    body: JSON.stringify({ case_id: currentCaseId, session_id: witnessState[idx].sessionId }),
  });

  const client = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });

  // Joining a channel does NOT auto-play other participants' audio -- the
  // agent's spoken replies only reach the speakers if we explicitly
  // subscribe to its published track here.
  client.on("user-published", async (user, mediaType) => {
    await client.subscribe(user, mediaType);
    if (mediaType === "audio") user.audioTrack.play();
  });

  await client.join(app_id, channel_name, frontend_token, frontend_uid);
  const micTrack = await AgoraRTC.createMicrophoneAudioTrack();
  await client.publish([micTrack]);

  witnessState[idx].agoraClient = client;
  witnessState[idx].micTrack = micTrack;

  if (idx === activeWitnessTab) {
    startMicVisualizer(micTrack);
    setVoiceState("On call — speak naturally");
    document.getElementById("orb").classList.add("live");
  }
}

function startMicVisualizer(micTrack) {
  const bars = document.querySelectorAll("#mic-indicator span");
  clearInterval(witnessState[activeWitnessTab]._visualizerInterval);
  const interval = setInterval(() => {
    const level = micTrack.getVolumeLevel(); // 0..1
    bars.forEach((bar, i) => {
      const jitter = Math.sin(Date.now() / 120 + i) * 0.15;
      const h = Math.max(4, Math.min(20, (level + jitter) * 60));
      bar.style.height = `${h}px`;
    });
  }, 100);
  witnessState[activeWitnessTab]._visualizerInterval = interval;
}

function setVoiceState(text) {
  document.getElementById("voice-state").textContent = text;
}

// ---------- Begin interview (case + witness 1 session + join, one click) ----------

document.getElementById("begin-btn").addEventListener("click", async () => {
  const incident_location = document.getElementById("incident-location").value.trim();
  const incident_description = document.getElementById("incident-description").value.trim();
  if (!incident_location) {
    alert("Incident location is required (used for jurisdiction lookup).");
    return;
  }

  const btn = document.getElementById("begin-btn");
  btn.disabled = true;
  btn.textContent = "Connecting…";

  try {
    const caseObj = await api("/cases", {
      method: "POST",
      body: JSON.stringify({ incident_location, incident_description }),
    });
    currentCaseId = caseObj.id;

    const session = await api(`/cases/${currentCaseId}/sessions`, {
      method: "POST",
      body: JSON.stringify({ witness_label: "Witness 1" }),
    });
    witnessState[0].sessionId = session.id;
    witnessState[0].label = "Witness 1";

    document.getElementById("setup-screen").style.display = "none";
    document.getElementById("conversation-screen").style.display = "block";
    document.getElementById("case-ref").textContent = `${caseObj.id} (${caseObj.reference_code})`;

    await joinWitnessVoice(0);
    startPolling();
  } catch (err) {
    console.error(err);
    btn.disabled = false;
    btn.textContent = "Begin interview";
    alert("Could not start the interview: " + err.message);
  }
});

// ---------- Second witness ----------

async function startWitness2() {
  if (witnessState[1].sessionId) return;
  const session = await api(`/cases/${currentCaseId}/sessions`, {
    method: "POST",
    body: JSON.stringify({ witness_label: "Witness 2" }),
  });
  witnessState[1].sessionId = session.id;
  witnessState[1].label = "Witness 2";
  document.getElementById("witness2-status").textContent = "Connecting…";
  document.getElementById("witness2-inline-btn").style.display = "none";
  try {
    await joinWitnessVoice(1);
    document.getElementById("witness2-status").innerHTML = "<b>On call</b>";
    renderWitnessTabs();
  } catch (err) {
    document.getElementById("witness2-status").textContent = "Failed to connect: " + err.message;
  }
}

document.getElementById("witness2-btn").addEventListener("click", startWitness2);
document.getElementById("witness2-inline-btn").addEventListener("click", startWitness2);

function renderWitnessTabs() {
  const heading = document.querySelector(".sketch-panel h3");
  if (!witnessState[1].sessionId) {
    heading.textContent = "Live composite — Witness 1";
    return;
  }
  heading.innerHTML = "";
  [0, 1].forEach((idx) => {
    const tab = document.createElement("span");
    tab.textContent = `Witness ${idx + 1}`;
    tab.style.cursor = "pointer";
    tab.style.marginRight = "0.8rem";
    tab.style.opacity = idx === activeWitnessTab ? "1" : "0.45";
    tab.addEventListener("click", () => {
      activeWitnessTab = idx;
      renderWitnessTabs();
      refreshState();
      if (witnessState[idx].micTrack) startMicVisualizer(witnessState[idx].micTrack);
    });
    heading.appendChild(tab);
  });
}

// ---------- Tools drawer ----------

const toolsToggle = document.getElementById("tools-toggle");
const toolsDrawer = document.getElementById("tools-drawer");
toolsToggle.addEventListener("click", () => {
  toolsToggle.classList.toggle("open");
  toolsDrawer.classList.toggle("open");
});

// ---------- Case tools actions ----------

document.getElementById("signoff-btn").addEventListener("click", async () => {
  const signed_off_by = document.getElementById("signoff-name").value.trim() || "Unnamed caseworker";
  try {
    await api(`/cases/${currentCaseId}/signoff`, { method: "POST", body: JSON.stringify({ signed_off_by }) });
    refreshState();
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("escalate-btn").addEventListener("click", async () => {
  const reason = document.getElementById("escalate-reason").value.trim() || "manually escalated from UI";
  try {
    await api(`/cases/${currentCaseId}/escalate`, { method: "POST", body: JSON.stringify({ reason }) });
    refreshState();
  } catch (e) {
    alert(e.message);
  }
});

document.getElementById("reconcile-btn").addEventListener("click", async () => {
  try {
    const result = await api(`/cases/${currentCaseId}/reconcile`, { method: "POST" });
    alert(
      result.conflicts.length
        ? `Found ${result.conflicts.length} conflicting field(s) — case escalated for human review.`
        : "Both witnesses agree on all shared features. No conflicts."
    );
    refreshState();
  } catch (e) {
    alert(e.message);
  }
});

// ---------- State polling & rendering ----------

function renderFeatureChips(container, params) {
  container.innerHTML = "";
  for (const [field, label] of Object.entries(FIELD_LABELS)) {
    const value = params[field];
    if (value == null) continue;
    const verbatim = params[`${field}_verbatim`] || "";
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.innerHTML = `${label}: <b>${value}</b><div class="chip-tooltip">"${verbatim}"</div>`;
    container.appendChild(chip);
  }
  (params.distinguishing_marks || []).forEach((mark) => {
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.innerHTML = `mark: <b>${mark}</b>`;
    container.appendChild(chip);
  });
  if (!container.children.length) {
    container.innerHTML = '<div class="chip" style="opacity:0.5">no details captured yet</div>';
  }
}

async function refreshState() {
  if (!currentCaseId) return;
  const state = await api(`/cases/${currentCaseId}/state`);

  const pill = document.getElementById("case-status-pill");
  pill.textContent = state.case.status;
  pill.className = "status-pill" + (state.case.status === "CONFIRMED" ? " confirmed" : "") + (state.case.status === "ESCALATED" ? " escalated" : "");
  document.getElementById("case-jurisdiction").textContent = state.case.jurisdiction_name;

  document.getElementById("escalation-banners").innerHTML = state.escalations
    .map((e) => `<div class="banner escalation">Escalated (${e.source}): ${e.reason}</div>`)
    .join("");
  document.getElementById("conflict-banners").innerHTML = state.conflicts
    .map((c) => `<div class="banner conflict">Conflict on "${c.field_name}": witness A said "${c.witness_a_value}", witness B said "${c.witness_b_value}" — needs human review</div>`)
    .join("");

  const w = state.witnesses.find((w) => w.session.id === witnessState[activeWitnessTab].sessionId);
  if (!w) return;

  renderFeatureChips(document.getElementById("feature-chips"), w.parameters);

  const img = document.getElementById("sketch-img");
  const placeholder = document.getElementById("sketch-placeholder");
  const overlay = document.getElementById("sketching-overlay");
  const watermark = document.getElementById("draft-watermark");

  overlay.classList.toggle("active", w.latest_sketch_status === "GENERATING");

  if (w.latest_sketch_status === "READY" && w.latest_sketch_url) {
    const newSrc = `${w.latest_sketch_url}?_=${Date.now()}`;
    if (img.dataset.baseUrl !== w.latest_sketch_url) {
      img.dataset.baseUrl = w.latest_sketch_url;
      img.onload = () => img.classList.add("shown");
      img.src = newSrc;
      placeholder.style.display = "none";
    }
    const isFinal = state.case.status === "CONFIRMED";
    watermark.classList.toggle("show", !isFinal);
  }

  if (state.case.status === "PENDING_REVIEW" || state.case.status === "CONFIRMED") {
    setVoiceState(state.case.status === "CONFIRMED" ? "Case confirmed" : "Description complete — awaiting sign-off");
  }
}

function startPolling() {
  refreshState();
  setInterval(refreshState, 1500);
}

checkBackend();
