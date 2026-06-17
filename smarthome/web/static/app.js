"use strict";

const $ = (sel) => document.querySelector(sel);
const DEVICE_KEYS = ["ac", "lights", "lock", "geyser", "plug"];

// --- API helpers -------------------------------------------------------------
async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (res.status === 401) throw { unauth: true };
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.status === 204 ? null : res.json();
}

// --- Boot: show dashboard if authenticated, else login -----------------------
async function boot() {
  try {
    await api("/api/users");
    showDashboard();
  } catch (e) {
    if (e.unauth) showLogin();
    else console.error(e);
  }
}

function showLogin() {
  $("#login").classList.remove("hidden");
  $("#dash").classList.add("hidden");
  if (new URLSearchParams(location.search).get("error")) $("#login-error").classList.remove("hidden");
}

function showDashboard() {
  $("#login").classList.add("hidden");
  $("#dash").classList.remove("hidden");
  loadUsers();
  refreshHaStatus();
}

// --- Tabs --------------------------------------------------------------------
document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab").forEach((t) => t.classList.add("hidden"));
    $("#tab-" + btn.dataset.tab).classList.remove("hidden");
    if (btn.dataset.tab === "logs") loadLogs();
    if (btn.dataset.tab === "stats") loadStats();
  });
});

// --- Users -------------------------------------------------------------------
async function loadUsers() {
  const users = await api("/api/users");
  if (!users.length) {
    $("#users-table").innerHTML = `<p class="muted">No users yet. Add one to get started.</p>`;
    return;
  }
  const rows = users.map((u) => {
    const devices = Object.keys(u.entities || {}).map((k) => `<span class="tag">${k}</span>`).join(" ") || "—";
    const id = u.whatsapp_number || u.id;
    return `<tr>
      <td><b>${u.flat}</b></td>
      <td>${u.name || "—"}</td>
      <td>${u.whatsapp_number || "—"}</td>
      <td>${u.telegram_id || "—"}</td>
      <td>${devices}</td>
      <td>${u.total_commands}</td>
      <td>${u.last_active || "never"}</td>
      <td><span class="linkish" data-del="${id}">remove</span></td>
    </tr>`;
  }).join("");
  $("#users-table").innerHTML = `<table>
    <thead><tr><th>Flat</th><th>Name</th><th>WhatsApp</th><th>Telegram</th>
    <th>Devices</th><th>Cmds</th><th>Last active</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>`;

  document.querySelectorAll("[data-del]").forEach((el) =>
    el.addEventListener("click", async () => {
      if (!confirm("Remove this user?")) return;
      await api("/api/users/" + encodeURIComponent(el.dataset.del), { method: "DELETE" });
      loadUsers();
    })
  );
}

$("#show-add").addEventListener("click", () => $("#add-form").classList.toggle("hidden"));
$("#cancel-add").addEventListener("click", () => $("#add-form").classList.add("hidden"));

$("#add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const entities = {};
  DEVICE_KEYS.forEach((k) => { if (f[k].value.trim()) entities[k] = f[k].value.trim(); });
  const body = {
    flat: f.flat.value.trim(),
    name: f.name.value.trim() || null,
    whatsapp_number: f.whatsapp_number.value.trim() || null,
    telegram_id: f.telegram_id.value.trim() ? Number(f.telegram_id.value.trim()) : null,
    entities,
  };
  try {
    await api("/api/users", { method: "POST", body: JSON.stringify(body) });
    f.reset();
    $("#add-form").classList.add("hidden");
    $("#add-error").classList.add("hidden");
    loadUsers();
  } catch (err) {
    $("#add-error").textContent = err.message || "Failed to add user.";
    $("#add-error").classList.remove("hidden");
  }
});

// --- Logs --------------------------------------------------------------------
async function loadLogs() {
  const logs = await api("/api/logs?limit=100");
  if (!logs.length) { $("#logs-table").innerHTML = `<p class="muted">No commands logged yet.</p>`; return; }
  const rows = logs.map((l) => `<tr>
    <td>${l.timestamp}</td>
    <td><span class="tag">${l.channel || "—"}</span></td>
    <td>${l.flat || "—"}</td>
    <td>${escapeHtml(l.raw_message || "")}</td>
    <td>${l.parse_source || "—"}</td>
    <td><code>${l.entity_id || "—"}</code></td>
    <td><span class="tag ${l.success ? "ok" : "bad"}">${l.success ? "ok" : "fail"}</span></td>
    <td>${l.latency_ms ?? "—"}ms</td>
  </tr>`).join("");
  $("#logs-table").innerHTML = `<table>
    <thead><tr><th>Time</th><th>Ch</th><th>Flat</th><th>Message</th>
    <th>Parser</th><th>Entity</th><th>Result</th><th>Latency</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}
$("#refresh-logs").addEventListener("click", loadLogs);

// --- Stats -------------------------------------------------------------------
async function loadStats() {
  const stats = await api("/api/stats");
  if (!stats.length) { $("#stats-table").innerHTML = `<p class="muted">No stats yet.</p>`; return; }
  const rows = stats.map((s) => {
    const rate = s.logged ? Math.round((100 * (s.successes || 0)) / s.logged) : 0;
    return `<tr>
      <td><b>${s.flat}</b></td>
      <td>${s.whatsapp_number || "—"}</td>
      <td>${s.total_commands}</td>
      <td>${rate}%</td>
      <td>${s.avg_latency_ms ? Math.round(s.avg_latency_ms) + "ms" : "—"}</td>
      <td>${s.last_active || "never"}</td>
    </tr>`;
  }).join("");
  $("#stats-table").innerHTML = `<table>
    <thead><tr><th>Flat</th><th>WhatsApp</th><th>Total cmds</th>
    <th>Success rate</th><th>Avg latency</th><th>Last active</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

// --- HA status ---------------------------------------------------------------
async function refreshHaStatus() {
  const pill = $("#ha-status");
  try {
    const s = await api("/api/ha/status");
    const up = s.home_assistant === "up";
    pill.textContent = "HA: " + (up ? "online" : "offline");
    pill.className = "pill " + (up ? "up" : "down");
  } catch { pill.textContent = "HA: ?"; }
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

boot();
