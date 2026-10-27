"use strict";
// CloudBuild Guardian — all displayed external/model content uses textContent, never innerHTML.
let apiToken = "";
let selected = "readiness";
let current = null;
let busy = false;
let toastTimer;

const $ = (id) => document.getElementById(id);
function element(tag, cls, text) {
  const out = document.createElement(tag);
  if (cls) out.className = cls;
  if (text !== undefined) out.textContent = String(text);
  return out;
}
function showToast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").classList.remove("visible"), 4500);
}
async function request(path, body) {
  const headers = {"Accept": "application/json"};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (apiToken) headers.Authorization = "Bearer " + apiToken;
  const options = {headers};
  if (body !== undefined) {
    options.method = "POST";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); } catch (_) { throw new Error("Unexpected server response"); }
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function run(action) {
  if (busy) return;
  busy = true;
  updateButtons();
  try { await action(); }
  catch (err) { showToast(err.message || "Operation failed"); }
  finally { busy = false; updateButtons(); }
}
async function initialize() {
  try {
    const state = await request("/api/status");
    $("engine-status").textContent = state.mode === "meta" ? "Meta Muse Spark 1.3" : "Scripted demo · no API spend";
    $("connection-label").textContent = "Local sandbox connected";
    $("connection-dot").className = "dot online";
    $("create-incident").disabled = false;
    renderScenarioList(state.scenarios || []);
  } catch (err) {
    $("connection-label").textContent = "Access required";
    $("connection-dot").className = "dot offline";
    $("engine-status").textContent = "Awaiting connection";
    showToast(err.message);
  }
}
function renderScenarioList(scenarios) {
  const list = $("scenario-list");
  list.replaceChildren();
  scenarios.forEach((s) => {
    const button = element("button", "scenario" + (s.id === selected ? " selected" : ""));
    button.type = "button";
    button.setAttribute("aria-pressed", String(s.id === selected));
    const head = element("div", "scenario-top");
    head.append(element("span", "scenario-title", s.name), element("span", "severity " + s.severity, s.severity));
    button.append(head, element("p", null, s.summary));
    button.addEventListener("click", () => {
      if (busy) return;
      selected = s.id;
      renderScenarioList(scenarios);
    });
    list.append(button);
  });
}
function addObservation(observation) {
  const row = element("article", "observation");
  const head = element("div", "observation-head");
  head.append(element("span", "obs-id", observation.id), element("span", "obs-source", observation.source));
  row.append(head, element("p", null, observation.text));
  return row;
}
function addEvent(event) {
  const row = element("div", "audit-event");
  row.append(element("strong", null, event.kind.replaceAll(".", " / ")));
  let detail = [];
  if (event.detail.action) detail.push("Action: " + event.detail.action);
  if (event.detail.source) detail.push("Source: " + event.detail.source);
  if (event.detail.passed !== undefined) detail.push("Proof: " + (event.detail.passed ? "PASS" : "FAIL"));
  if (event.detail.reason) detail.push(event.detail.reason);
  if (detail.length) row.append(element("p", null, detail.join(" · ")));
  row.append(element("span", "event-time", "#" + event.seq + " · " + event.timestamp));
  return row;
}
function updateSteps(stage) {
  const levels = {
    detected: 0, awaiting_approval: 1, applied_simulation: 2,
    rejected: 2, verified: 3, failed_verification: 3
  };
  const n = levels[stage] ?? -1;
  ["detect", "reason", "approve", "verify"].forEach((label, index) => {
    const el = $("step-" + label);
    el.className = "step" + (index < n ? " done" : "") + (index === n ? " active" : "");
  });
}
function updateButtons() {
  $("create-incident").disabled = busy || $("connection-dot").className !== "dot online";
  const stage = current?.stage || "";
  $("investigate").hidden = stage !== "detected";
  $("approve").hidden = stage !== "awaiting_approval";
  $("reject").hidden = stage !== "awaiting_approval";
  $("verify").hidden = stage !== "applied_simulation";
  for (const id of ["investigate", "approve", "reject", "verify"]) $(id).disabled = busy;
}
async function updateLedger() {
  if (!current) return;
  try {
    const result = await request("/api/ledger", {id: current.id});
    $("integrity-status").textContent = result.ledger_intact ? "Chain verified ✓" : "Chain invalid ✗";
    $("integrity-status").style.color = result.ledger_intact ? "#45f4d2" : "#ff7c91";
  } catch (err) {
    $("integrity-status").textContent = "Verification unavailable";
  }
}
async function render() {
  if (!current) return;
  const s = current;
  $("empty-state").hidden = true;
  $("incident-detail").hidden = false;
  $("current-title").textContent = s.title + " · " + s.namespace + "/" + s.service;
  $("stage-badge").textContent = s.stage.replaceAll("_", " ").toUpperCase();
  $("incident-counter").textContent = s.id.slice(0, 8);
  updateSteps(s.stage);
  const obs = $("observations");
  obs.replaceChildren(...s.observations.map(addObservation));
  $("observation-count").textContent = s.observations.length + " RECORDS";
  $("diagnosis-section").hidden = !s.diagnosis;
  if (s.diagnosis) {
    $("root-cause").textContent = s.diagnosis.root_cause;
    $("reasoning").textContent = s.diagnosis.reasoning;
    $("diagnosis-source").textContent = s.diagnosis.source.startsWith("meta:")
      ? "◈ META MODEL API • REAL INFERENCE" : "◇ SCRIPTED FIXTURE • NOT AI";
    $("evidence-chips").replaceChildren(...s.diagnosis.evidence_ids.map((id) => element("span", null, id)));
  }
  $("proposal-section").hidden = !s.proposal;
  if (s.proposal) {
    $("proposal-action").textContent = s.proposal.action;
    $("patch-preview").textContent = s.proposal.patch_preview;
  }
  $("verification-section").hidden = !s.validation;
  if (s.validation) {
    $("verification-title").textContent = s.validation.passed ? "Simulated recovery verified" : "Verification failed";
    $("verification-symbol").textContent = s.validation.passed ? "✓" : "✕";
    $("verification-proof").textContent = s.validation.proof;
  }
  $("audit-events").replaceChildren(...s.events.map(addEvent));
  $("audit-short-hash").textContent = s.events.at(-1)?.hash.slice(0, 25) + "…" || "Not initialized";
  updateButtons();
  await updateLedger();
}
async function createIncident() {
  current = await request("/api/incidents", {scenario: selected});
  await render();
  showToast("Synthetic incident created. Evidence captured.");
}
async function investigate() {
  if (!current) return;
  const id = current.id;
  const result = await request("/api/investigate", {id});
  current = result;
  await render();
  showToast(result.diagnosis.source.startsWith("meta:")
    ? "Muse Spark diagnosis reviewed by deterministic safety gate."
    : "Scripted fixture analysis ready. No AI credits spent.");
}
async function approve(approved) {
  if (!current) return;
  current = await request("/api/approve", {id: current.id, revision: current.revision, approved});
  await render();
  showToast(approved ? "Approved sandbox-only patch applied." : "Proposal rejected. No change made.");
}
async function verify() {
  if (!current) return;
  current = await request("/api/verify", {id: current.id});
  await render();
  showToast(current.validation?.passed ? "Verified synthetic recovery and audit integrity." : "Verification failed.");
}

$("create-incident").addEventListener("click", () => run(createIncident));
$("investigate").addEventListener("click", () => run(investigate));
$("approve").addEventListener("click", () => run(() => approve(true)));
$("reject").addEventListener("click", () => run(() => approve(false)));
$("verify").addEventListener("click", () => run(verify));
$("connect").addEventListener("click", () => {
  apiToken = $("access-token").value;
  $("access-token").value = "";
  run(initialize);
});
initialize();
