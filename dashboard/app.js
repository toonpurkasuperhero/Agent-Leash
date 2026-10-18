/* AgentLeash console — vanilla JS, no build step. */
"use strict";

// ----------------------------------------------------------------- helpers
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtInt = (n) => (n ?? 0).toLocaleString();
const pct = (x) => `${Math.round((x ?? 0) * 100)}%`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, opts = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...opts };
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data;
}

function ago(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(ts * 1000).toLocaleDateString();
}
const clock = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const argsLine = (args) => Object.entries(args || {}).map(([k, v]) => `${k}=${typeof v === "string" ? JSON.stringify(v.length > 90 ? v.slice(0, 90) + "…" : v) : JSON.stringify(v)}`).join("  ");

function toast(msg, kind = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `${icon(kind === "ok" ? "check-circle" : "alert")}<div>${esc(msg)}</div>`;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

// ------------------------------------------------------------------- icons
const P = {
  overview: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  lab: '<path d="M9 3h6M10 3v6l-5.5 9.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3"/><path d="M7.5 15h9"/>',
  feed: '<path d="M4 6h16M4 12h10M4 18h16"/><circle cx="18" cy="12" r="2"/>',
  approvals: '<path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8a8 8 0 0 0 16 0v-3a2 2 0 0 0-4 0"/>',
  agents: '<rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4M9 12h.01M15 12h.01M9 16h6"/>',
  policies: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
  eval: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  audit: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  check: '<path d="M5 12.5l4.2 4.2L19 7"/>',
  "check-circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16.5 9.5"/>',
  "shield-x": '<path d="M12 3 4.5 6v6c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/>',
  "shield-check": '<path d="M12 3 4.5 6v6c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z"/><path d="M8.8 12.3l2.3 2.3 4.4-4.6"/>',
  hand: '<path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8a8 8 0 0 0 16 0v-3a2 2 0 0 0-4 0"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  play: '<path d="M7 4v16l13-8z"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M10.8 12.2 20 3M16 7l3 3M14 9l2 2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13l3.5 7v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  pen: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 3 3h0a3 3 0 0 0 3-3V7a3 3 0 0 0-3-3zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-3 3h0a3 3 0 0 1-3-3"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  unlock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.8-1.2"/>',
  zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
};
const TOOL_ICON = { read_file: "file", list_files: "folder", write_file: "pen", delete_file: "trash", query_db: "db", send_email: "mail", http_get: "globe", read_inbox: "inbox" };
function icon(name, cls = "") {
  return `<svg class="${cls}" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || ""}</svg>`;
}

const VERDICT = {
  ALLOW: { cls: "allow", label: "Allowed", icon: "check" },
  DENY: { cls: "deny", label: "Blocked", icon: "shield-x" },
  NEEDS_APPROVAL: { cls: "held", label: "Held", icon: "hand" },
};
function chip(verdict, opts = {}) {
  if (opts.mode === "learn") return `<span class="chip learn">${icon("brain")}Learning</span>`;
  if (opts.simulated && opts.simulated !== "ALLOW") {
    const v = VERDICT[opts.simulated];
    return `<span class="chip ${v.cls} sim" title="Simulate mode: would have been ${v.label.toLowerCase()}">${icon(v.icon)}Would ${v.label.toLowerCase().replace("held", "hold")}</span>`;
  }
  if (!verdict) return `<span class="chip">${icon("unlock")}Unchecked</span>`;
  const v = VERDICT[verdict] || VERDICT.ALLOW;
  let label = v.label;
  if (verdict === "NEEDS_APPROVAL" && opts.approval) label = { approved: "Approved", denied: "Denied by human", expired: "Expired", pending: "Awaiting human" }[opts.approval] || label;
  return `<span class="chip ${v.cls}">${icon(v.icon)}${esc(label)}</span>`;
}
const modePill = (m) => `<span class="mode ${esc(m)}">${esc(m[0].toUpperCase() + m.slice(1))}</span>`;
function scoreBar(s) {
  if (s === null || s === undefined) return '<span class="dim">—</span>';
  const cls = s >= 0.9 ? "hot" : s >= 0.6 ? "warm" : "";
  return `<span class="score ${cls}"><span class="bar"><i style="width:${Math.round(s * 100)}%"></i></span><span class="tnum">${s.toFixed(2)}</span></span>`;
}
const REASON_LABEL = {
  tool_not_in_policy: "tool never granted", tool_not_allowed: "tool disabled", path_outside_policy: "path outside policy",
  recipient_not_allowed: "recipient not allowed", host_not_allowed: "host not allowed", sql_not_readonly: "write on read-only",
  sql_op_not_allowed: "SQL op not allowed", sql_table_not_allowed: "table not allowed", sql_unbounded_write: "unbounded write",
  rate_limit: "rate limit", forbidden_sequence: "data-flow rule", outside_task_scope: "outside task scope",
  tainted_high_risk: "after untrusted input", anomalous: "anomalous", learning: "learning", gateway_unreachable: "gateway down",
};
const reasonTags = (rs) => (rs || []).filter((r) => r !== "learning").map((r) => `<span class="tag">${esc(REASON_LABEL[r] || r)}</span>`).join(" ");

// ------------------------------------------------------------------- state
const state = { config: null, stats: null, agents: [], page: "overview", timers: [], lab: { tab: "attacks", selected: "A01", protected: true, compare: true, agentMode: "scripted", runs: {}, running: false, custom: "" }, feed: { verdict: "", agent: "", q: "" }, policy: { agent: null, selected: null }, scenarios: null };

function every(fn, ms) { fn(); const id = setInterval(fn, ms); state.timers.push(id); }
function clearTimers() { state.timers.forEach(clearInterval); state.timers = []; }

// ------------------------------------------------------------------ router
const PAGES = [
  { id: "overview", label: "Overview", icon: "overview", sub: "What your agents did, and what AgentLeash stopped" },
  { id: "lab", label: "Attack Lab", icon: "lab", sub: "Run real attack scenarios against a sandboxed company, with and without protection" },
  { id: "feed", label: "Live Feed", icon: "feed", sub: "Every tool call, every decision, every reason" },
  { id: "approvals", label: "Approvals", icon: "approvals", sub: "Risky actions waiting for a human" },
  { section: "Control" },
  { id: "agents", label: "Agents", icon: "agents", sub: "Permissions granted vs. actually needed" },
  { id: "policies", label: "Policies", icon: "policies", sub: "Least-privilege policies learned from behaviour — reviewable as code" },
  { id: "eval", label: "Evaluation", icon: "eval", sub: "Benchmark: attack success and legitimate-work completion across defences" },
  { id: "audit", label: "Audit Log", icon: "audit", sub: "Tamper-evident, hash-chained record of every decision" },
];

function renderNav() {
  $("#nav").innerHTML = PAGES.map((p) => p.section
    ? `<div class="nav-section">${esc(p.section)}</div>`
    : `<a href="#/${p.id}" data-page="${p.id}" class="${state.page === p.id ? "active" : ""}">${icon(p.icon)}<span class="lbl">${esc(p.label)}</span>${p.id === "approvals" ? '<span class="badge" id="nav-badge" hidden>0</span>' : ""}</a>`).join("");
  updateBadge();
}

function updateBadge() {
  const b = $("#nav-badge");
  if (!b || !state.stats) return;
  const n = state.stats.pending_approvals;
  b.hidden = !n;
  b.textContent = n;
}

async function route() {
  const id = (location.hash.replace(/^#\/?/, "") || "overview").split("?")[0];
  const page = PAGES.find((p) => p.id === id) || PAGES[0];
  clearTimers();
  closeDrawer();
  state.page = page.id;
  renderNav();
  $("#page-title").textContent = page.label;
  $("#page-sub").textContent = page.sub;
  $("#topbar-actions").innerHTML = "";
  $("#view").innerHTML = "";
  $("#view").style.animation = "none"; void $("#view").offsetWidth; $("#view").style.animation = "";
  try { await VIEWS[page.id]($("#view")); } catch (e) { $("#view").innerHTML = `<div class="card empty">${icon("alert")}${esc(e.message)}</div>`; }
}

// --------------------------------------------------------------- global poll
async function pollGlobal() {
  try {
    state.stats = await api("/api/stats");
    updateBadge();
    const llm = state.config?.llm;
    $("#llm-status").innerHTML = `<span class="dot ${llm ? "on" : ""}"></span>${llm ? "Claude: scoping + explanations" : "Offline mode (rules + heuristics)"}`;
  } catch (e) { $("#llm-status").innerHTML = `<span class="dot"></span>Gateway unreachable`; }
}

function topActions(html) { $("#topbar-actions").innerHTML = html; }

async function oneClickSetup(btn) {
  if (btn) { btn.disabled = true; btn.innerHTML = `<span class="spin"></span>Learning…`; }
  await api("/api/lab/learn", { method: "POST", body: { enforce: true } });
  for (;;) {
    await sleep(500);
    const j = await api("/api/lab/learn");
    if (btn) btn.innerHTML = `<span class="spin"></span>Learning ${pct(j.progress)}`;
    if (j.status !== "running") {
      if (j.status === "error") throw new Error(j.message);
      break;
    }
  }
  toast("Learned normal behaviour, generated policies, and switched agents to enforce.");
}

async function resetDemo() {
  if (!confirm("Reset the demo? This clears all events, policies, approvals, the audit log and the sandbox.")) return;
  await api("/api/demo/reset", { method: "POST" });
  state.lab.runs = {};
  toast("Demo reset — agents are back in learning mode.");
  route();
}

const setupButtons = () => `
  <button class="btn" id="btn-reset">${icon("refresh")}Reset demo</button>
  <button class="btn primary" id="btn-setup">${icon("sparkle")}One-click setup</button>`;
function bindSetupButtons() {
  $("#btn-reset")?.addEventListener("click", resetDemo);
  $("#btn-setup")?.addEventListener("click", async (e) => {
    try { await oneClickSetup(e.currentTarget); } catch (err) { toast(err.message, "err"); }
    route();
  });
}

// ------------------------------------------------------------------ charts
const tip = $("#tooltip");
function showTip(html, evt) {
  tip.innerHTML = html;
  tip.hidden = false;
  const r = tip.getBoundingClientRect();
  let x = evt.clientX + 14, y = evt.clientY + 14;
  if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = evt.clientY - r.height - 14;
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
}
const hideTip = () => { tip.hidden = true; };
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function niceMax(v) {
  if (v <= 4) return 4;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
function topRounded(x, y, w, h, r) {
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

function stackedBars(el, buckets, series, bucketSeconds) {
  const W = Math.max(320, el.clientWidth), H = 230, m = { t: 12, r: 8, b: 26, l: 34 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const totals = buckets.map((b) => series.reduce((s, k) => s + b[k.key], 0));
  const max = niceMax(Math.max(1, ...totals));
  const bw = iw / buckets.length, barW = Math.max(3, Math.min(26, bw * 0.62));
  const y = (v) => m.t + ih - (v / max) * ih;
  let g = '<g class="grid">';
  for (let i = 0; i <= 4; i++) {
    const v = (max / 4) * i, yy = y(v);
    g += `<line x1="${m.l}" x2="${W - m.r}" y1="${yy}" y2="${yy}"/><text x="${m.l - 8}" y="${yy + 4}" text-anchor="end" class="tnum">${Math.round(v)}</text>`;
  }
  g += "</g>";
  let bars = "", hits = "", labels = "";
  buckets.forEach((b, i) => {
    const cx = m.l + bw * i + bw / 2, x = cx - barW / 2;
    let acc = 0;
    const segs = series.filter((s) => b[s.key] > 0);
    segs.forEach((s, j) => {
      const v = b[s.key];
      const y0 = y(acc + v), h = (v / max) * ih;
      const gap = j > 0 ? 2 : 0;
      const top = j === segs.length - 1;
      bars += top
        ? `<path d="${topRounded(x, y0, barW, Math.max(1, h - gap), 4)}" fill="${s.color}"/>`
        : `<rect x="${x}" y="${y0}" width="${barW}" height="${Math.max(1, h - gap)}" fill="${s.color}"/>`;
      acc += v;
    });
    hits += `<rect class="hit" data-i="${i}" x="${m.l + bw * i}" y="${m.t}" width="${bw}" height="${ih}"/>`;
    if (i % Math.ceil(buckets.length / 6) === 0) labels += `<text x="${cx}" y="${H - 8}" text-anchor="middle">${clock(b.t)}</text>`;
  });
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="Decisions over time">${g}<line class="baseline" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"/>${bars}${labels}${hits}</svg>`;
  $$(".hit", el).forEach((r) => {
    r.addEventListener("mousemove", (e) => {
      const b = buckets[+r.dataset.i];
      showTip(`<div class="t">${clock(b.t)} – ${clock(b.t + bucketSeconds)}</div>` + series.map((s) => `<div class="r"><span><i style="background:${s.color}"></i>${s.label}</span><b class="tnum">${b[s.key]}</b></div>`).join(""), e);
    });
    r.addEventListener("mouseleave", hideTip);
  });
}

function hbars(el, items, { max = 1, format = (v) => v } = {}) {
  const W = Math.max(280, el.clientWidth), rowH = 42, m = { l: 150, r: 112 };
  const H = items.length * rowH + 8, iw = W - m.l - m.r;
  const color = cssVar("--series-1");
  let out = "";
  items.forEach((it, i) => {
    const yy = 6 + i * rowH, w = Math.max(it.value > 0 ? 4 : 0, (it.value / max) * iw);
    out += `<text x="${m.l - 12}" y="${yy + 19}" text-anchor="end" class="label-2">${esc(it.label)}</text>`;
    out += `<rect x="${m.l}" y="${yy + 6}" width="${iw}" height="20" rx="4" fill="${cssVar("--surface-3")}"/>`;
    if (w > 0) out += `<rect x="${m.l}" y="${yy + 6}" width="${w}" height="20" rx="4" fill="${color}"><title>${esc(it.label)}: ${esc(it.text || format(it.value))}</title></rect>`;
    out += `<text x="${m.l + Math.max(w, 0) + 8}" y="${yy + 21}" class="label-ink tnum">${esc(it.text || format(it.value))}</text>`;
  });
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img">${out}</svg>`;
}

function stripPlot(el, points, thresholds) {
  const W = Math.max(320, el.clientWidth), H = 200, m = { t: 22, r: 16, b: 28, l: 110 };
  const iw = W - m.l - m.r;
  const rows = [{ key: "benign", label: "Normal tasks", color: cssVar("--series-1") }, { key: "attack", label: "Attack runs", color: cssVar("--series-2") }];
  const rowY = (i) => m.t + 30 + i * 62;
  const x = (v) => m.l + v * iw;
  let g = '<g class="grid">';
  for (let i = 0; i <= 5; i++) { const v = i / 5; g += `<line x1="${x(v)}" x2="${x(v)}" y1="${m.t}" y2="${H - m.b}"/><text x="${x(v)}" y="${H - 8}" text-anchor="middle" class="tnum">${v.toFixed(1)}</text>`; }
  g += "</g>";
  let th = "";
  thresholds.forEach((t) => {
    th += `<line x1="${x(t.v)}" x2="${x(t.v)}" y1="${m.t - 6}" y2="${H - m.b}" stroke="${t.color}" stroke-width="1.5" stroke-dasharray="4 3"/><text x="${x(t.v) + 5}" y="${m.t - 9}" class="label-2">${esc(t.label)} ≥ ${t.v}</text>`;
  });
  let dots = "";
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  rows.forEach((row, i) => {
    dots += `<text x="${m.l - 14}" y="${rowY(i) + 4}" text-anchor="end" class="label-ink">${row.label}</text>`;
    points.filter((p) => p.kind === row.key).forEach((p, j) => {
      const jy = rowY(i) + (rand() - 0.5) * 30;
      dots += `<circle cx="${x(Math.min(1, p.score))}" cy="${jy}" r="5" fill="${row.color}" stroke="${cssVar("--chart-surface")}" stroke-width="2" data-k="${row.key}" data-j="${j}" class="pt"/>`;
    });
  });
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="Anomaly score distribution">${g}${th}${dots}</svg>`;
  const byKind = { benign: points.filter((p) => p.kind === "benign"), attack: points.filter((p) => p.kind === "attack") };
  $$(".pt", el).forEach((c) => {
    c.addEventListener("mousemove", (e) => {
      const p = byKind[c.dataset.k][+c.dataset.j];
      showTip(`<div class="t">${esc(p.scenario)} · ${esc(p.tool)}</div><div class="r"><span>Anomaly score</span><b class="tnum">${p.score.toFixed(2)}</b></div><div class="r"><span>Verdict</span><b>${esc(VERDICT[p.verdict]?.label || p.verdict)}</b></div>`, e);
    });
    c.addEventListener("mouseleave", hideTip);
  });
}

// ------------------------------------------------------------------ drawer
function openDrawer(html) {
  $("#drawer").innerHTML = html;
  $("#drawer").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
  $("#drawer-backdrop").hidden = false;
  $("#drawer [data-close]")?.addEventListener("click", closeDrawer);
}
function closeDrawer() {
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#drawer-backdrop").hidden = true;
}
$("#drawer-backdrop").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

async function showEvent(id) {
  const e = await api(`/api/events/${id}`);
  const factors = (e.anomaly_factors || []).map((f) => `<div class="factor"><span>${esc(f.name.replace(/_/g, " "))}</span><span class="bar"><i style="width:${f.score * 100}%"></i></span><span class="tnum">${f.score.toFixed(2)}</span></div><div class="dim" style="font-size:12px;margin:-2px 0 6px 140px">${esc(f.detail)}</div>`).join("");
  openDrawer(`
    <div class="row between"><div><div class="dim mono" style="font-size:12px">${esc(e.event_id)} · ${new Date(e.ts * 1000).toLocaleString()}</div><h2 class="mono">${esc(e.tool)}</h2></div><button class="icon-btn" data-close aria-label="Close">${icon("x")}</button></div>
    <div class="row" style="margin-top:12px">${chip(e.verdict, { mode: e.mode, simulated: e.simulated_verdict, approval: e.approval?.status })}${modePill(e.mode)}<span class="tag">${esc(e.agent_id)}</span><span class="tag">risk: ${esc(e.risk)}</span></div>
    ${e.explanation ? `<div class="explain ${e.verdict === "NEEDS_APPROVAL" || e.simulated_verdict === "NEEDS_APPROVAL" ? "held" : ""}">${icon("sparkle")}<div>${esc(e.explanation)}</div></div>` : ""}
    <section><h4>User task</h4><div>${esc(e.task)}</div></section>
    <section><h4>Arguments</h4><pre class="code">${esc(JSON.stringify(e.args, null, 2))}</pre></section>
    ${(e.reason_details || []).length ? `<section><h4>Why</h4><div class="stack" style="gap:6px">${e.reasons.map((r, i) => `<div class="row" style="align-items:flex-start;flex-wrap:nowrap"><span class="tag">${esc(REASON_LABEL[r] || r)}</span><span class="muted" style="font-size:13px">${esc(e.reason_details[i] || "")}</span></div>`).join("")}</div></section>` : ""}
    <section><h4>Anomaly score · ${e.anomaly_score?.toFixed(2) ?? "—"}</h4>${factors || '<div class="dim">No deviation from the learned baseline.</div>'}</section>
    <section><h4>Task scope granted</h4><div class="row" style="gap:5px">${(e.scope || []).map((t) => `<span class="tag ${t === e.tool ? "used" : ""}">${esc(t)}</span>`).join("") || '<span class="dim">— (learning mode)</span>'}</div></section>
    <section><h4>Untrusted input in session</h4>${(e.taint_sources || []).length ? e.taint_sources.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ") : '<span class="dim">None</span>'}</section>
    <section><h4>Decision latency</h4><span class="tnum">${e.latency_ms?.toFixed(2)} ms</span> <span class="dim">(excluding explanation)</span></section>`);
}

// =================================================================== VIEWS
const VIEWS = {};

// ---------------------------------------------------------------- overview
VIEWS.overview = async (root) => {
  topActions(setupButtons());
  bindSetupButtons();
  root.innerHTML = `
    <div id="onboard"></div>
    <div class="grid cols-5" id="kpis"></div>
    <div class="grid split">
      <div class="card">
        <div class="card-h"><div><h2>Decisions, last hour</h2><div class="sub">Tool calls checked by the gateway, by verdict</div></div>
          <div class="legend"><span><i style="background:var(--good)"></i>Allowed</span><span><i style="background:var(--warning)"></i>Held for approval</span><span><i style="background:var(--critical)"></i>Blocked</span></div></div>
        <div class="chart-wrap" id="timeline"></div>
      </div>
      <div class="card"><div class="card-h"><div><h2>Latest interventions</h2><div class="sub">Blocked or held actions, with the reason</div></div><a class="btn sm ghost" href="#/feed">View all</a></div><div class="feed" id="interventions"></div></div>
    </div>
    <div class="grid cols-2" id="agent-strip"></div>`;

  every(async () => {
    const [s, agents] = await Promise.all([api("/api/stats"), api("/api/agents")]);
    state.stats = s; state.agents = agents;
    const enforced = agents.filter((a) => a.mode === "enforce").length;
    const hasPolicy = agents.some((a) => a.policy_version);
    const learned = agents.some((a) => a.baseline.events > 0);
    $("#onboard").innerHTML = enforced === agents.length && agents.length ? "" : `
      <div class="card hero glow">
        <div><h2>Put your agents on a leash in three steps</h2>
          <p>AgentLeash watches what each agent normally does, turns that into a least-privilege policy, then enforces it per task. Every block comes with a plain-English reason.</p>
          <div class="steps">
            <span class="step ${learned ? "done" : "current"}"><span class="num">${learned ? "✓" : 1}</span>Learn normal behaviour</span>
            <span class="step ${hasPolicy ? "done" : learned ? "current" : ""}"><span class="num">${hasPolicy ? "✓" : 2}</span>Generate least-privilege policy</span>
            <span class="step ${enforced ? "done" : hasPolicy ? "current" : ""}"><span class="num">${enforced ? "✓" : 3}</span>Enforce at runtime</span>
          </div></div>
        <button class="btn primary lg" id="hero-setup">${icon("sparkle")}Run all three</button>
      </div>`;
    $("#hero-setup")?.addEventListener("click", async (e) => { try { await oneClickSetup(e.currentTarget); } catch (err) { toast(err.message, "err"); } route(); });

    const removed = s.permissions_granted ? 1 - s.permissions_used / s.permissions_granted : 0;
    const v = s.verdicts;
    $("#kpis").innerHTML = [
      { label: "Tool calls checked", icon: "eye", value: fmtInt(s.events), foot: `${s.agents} agents connected` },
      { label: "Blocked", icon: "shield-x", value: fmtInt(v.DENY), foot: s.simulated_blocks ? `+${s.simulated_blocks} in simulate mode` : "Hard policy denials" },
      { label: "Held for a human", icon: "hand", value: fmtInt(v.NEEDS_APPROVAL), foot: `${s.pending_approvals} waiting now` },
      { label: "Permissions removable", icon: "key", value: `${Math.round(removed * 100)}<small>%</small>`, foot: `${s.permissions_used} of ${s.permissions_granted} grants ever used` },
      { label: "Decision latency (p50)", icon: "clock", value: s.latency_p50_ms != null ? `${s.latency_p50_ms}<small>ms</small>` : "—", foot: s.latency_p95_ms != null ? `p95 ${s.latency_p95_ms} ms` : "No enforced calls yet" },
    ].map((k) => `<div class="card kpi"><div class="label">${icon(k.icon)}${k.label}</div><div class="value tnum">${k.value}</div><div class="foot">${k.foot}</div></div>`).join("");

    $("#agent-strip").innerHTML = agents.map((a) => {
      const usedPct = a.granted ? (a.used / a.granted) * 100 : 0;
      return `<div class="card"><div class="card-h"><div><h3 class="mono">${esc(a.agent_id)}</h3><div class="sub">${esc(a.description)}</div></div>${modePill(a.mode)}</div>
        <div class="meter" title="${a.used} of ${a.granted} permissions used"><i style="width:${usedPct}%"></i></div>
        <div class="meter-legend"><span class="used">${a.used} permissions used</span><span>${a.granted - a.used} granted but never used</span><span class="dim">${fmtInt(a.events)} calls · ${a.denied} blocked · ${a.held} held</span></div></div>`;
    }).join("");
  }, 3000);

  every(async () => {
    const t = await api("/api/timeline?window=3600&buckets=30");
    const el = $("#timeline");
    if (!el) return;
    const any = t.buckets.some((b) => b.ALLOW + b.DENY + b.NEEDS_APPROVAL > 0);
    if (!any) { el.innerHTML = `<div class="empty">${icon("eval")}No enforced tool calls in the last hour. Run something in the <a href="#/lab">Attack Lab</a>.</div>`; return; }
    stackedBars(el, t.buckets, [
      { key: "ALLOW", label: "Allowed", color: cssVar("--good") },
      { key: "NEEDS_APPROVAL", label: "Held", color: cssVar("--warning") },
      { key: "DENY", label: "Blocked", color: cssVar("--critical") },
    ], t.bucket_s);
  }, 5000);

  every(async () => {
    const rows = await api("/api/events?verdict=BLOCKED&limit=6");
    const el = $("#interventions");
    if (!el) return;
    el.innerHTML = rows.length ? rows.map((e) => {
      const v = e.simulated_verdict || e.verdict;
      return `<div class="feed-item clickable" data-id="${e.event_id}" style="cursor:pointer"><div class="ic ${v === "DENY" ? "deny" : "held"}">${icon(TOOL_ICON[e.tool] || "zap")}</div>
        <div><div class="meta"><span class="mono">${esc(e.agent_id)}</span><span>·</span><span>${ago(e.ts)}</span>${chip(e.verdict, { simulated: e.simulated_verdict, approval: e.approval_status })}</div>
        <div class="title mono">${esc(e.tool)} <span class="dim" style="font-weight:400">${esc(argsLine(e.args).slice(0, 70))}</span></div>
        <p>${esc(e.explanation || "")}</p></div></div>`;
    }).join("") : `<div class="empty">${icon("shield-check")}Nothing blocked yet.</div>`;
    $$(".feed-item", el).forEach((r) => r.addEventListener("click", () => showEvent(r.dataset.id)));
  }, 4000);
};

// --------------------------------------------------------------------- lab
VIEWS.lab = async (root) => {
  topActions(setupButtons());
  bindSetupButtons();
  if (!state.scenarios) state.scenarios = await api("/api/scenarios");
  const L = state.lab;
  root.innerHTML = `
    <div id="lab-banner"></div>
    <div id="approval-banner"></div>
    <div class="grid lab-grid">
      <div class="card stack">
        <div class="seg" id="lab-tabs"><button data-tab="attacks">Attacks (${state.scenarios.attacks.length})</button><button data-tab="benign">Normal tasks (${state.scenarios.benign.length})</button>${state.config.llm ? '<button data-tab="custom">Custom</button>' : ""}</div>
        <div id="lab-picker"></div>
        <div class="sep" style="margin:4px 0"></div>
        <label class="switch"><input type="checkbox" id="sw-protect"><span class="track"></span><span><b>AgentLeash protection</b><br><small class="dim">Route every tool call through the gateway</small></span></label>
        <label class="switch"><input type="checkbox" id="sw-compare"><span class="track"></span><span><b>Side-by-side</b><br><small class="dim">Run unprotected, then protected</small></span></label>
        <div><span class="label-sm">Agent brain</span><div class="seg" id="agent-mode"><button data-m="scripted">Simulated LLM</button><button data-m="claude" ${state.config.llm ? "" : 'disabled title="Set ANTHROPIC_API_KEY to enable"'}>Claude</button></div>
          <div class="dim" style="font-size:12px;margin-top:6px" id="mode-hint"></div></div>
        <button class="btn primary lg block" id="btn-run">${icon("play")}Run scenario</button>
      </div>
      <div class="card" id="lab-trace"></div>
      <div class="stack lab-side">
        <div class="card"><div class="card-h"><div><h3>Company impact</h3><div class="sub">Damage measured in the sandbox</div></div></div><div id="lab-impact"></div></div>
        <div class="card"><div class="card-h"><div><h3>Sandbox state</h3><div class="sub">Fake company: files, prod DB, outbox, web</div></div><button class="btn sm" id="btn-sb-reset">${icon("refresh")}Reset</button></div><div id="lab-sandbox"></div></div>
      </div>
    </div>`;

  const sync = () => {
    $$("#lab-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === L.tab));
    $$("#agent-mode button").forEach((b) => b.classList.toggle("on", b.dataset.m === L.agentMode));
    $("#sw-protect").checked = L.protected;
    $("#sw-compare").checked = L.compare;
    $("#sw-protect").disabled = L.compare;
    $("#mode-hint").textContent = L.agentMode === "claude"
      ? `A real ${state.config.agent_model} agent decides which tools to call.`
      : "Deterministic agent that obeys instructions hidden in content — like a prompt-injectable model.";
    renderPicker();
  };
  const renderPicker = () => {
    const el = $("#lab-picker");
    if (L.tab === "custom") {
      el.innerHTML = `<span class="label-sm">Task for the Claude agent</span><textarea id="custom-task" rows="4" style="width:100%" placeholder="e.g. Summarize my inbox and handle anything urgent">${esc(L.custom)}</textarea>
        <span class="label-sm" style="margin-top:10px">Agent</span><select id="custom-agent" style="width:100%"><option>finance-assistant</option><option>support-bot</option></select>`;
      $("#custom-task").addEventListener("input", (e) => (L.custom = e.target.value));
      return;
    }
    const list = state.scenarios[L.tab];
    el.innerHTML = `<div class="scenario-list">${list.map((s) => `
      <button class="scenario ${L.selected === s.id ? "on" : ""}" data-id="${s.id}">
        <div class="row between"><span class="tag">${esc(s.id)}</span><span class="dim" style="font-size:11.5px">${esc(s.category || s.split || "")}</span></div>
        <b style="margin-top:5px">${esc(s.name)}</b><small>${esc(s.agent)} · “${esc(s.task)}”</small>
      </button>`).join("")}</div>`;
    $$(".scenario", el).forEach((b) => b.addEventListener("click", () => { L.selected = b.dataset.id; renderPicker(); }));
  };
  $$("#lab-tabs button").forEach((b) => b.addEventListener("click", () => { L.tab = b.dataset.tab; if (L.tab !== "custom") { L.selected = state.scenarios[L.tab][0].id; } else { L.agentMode = "claude"; L.compare = false; } sync(); }));
  $$("#agent-mode button").forEach((b) => b.addEventListener("click", () => { if (!b.disabled) { L.agentMode = b.dataset.m; sync(); } }));
  $("#sw-protect").addEventListener("change", (e) => (L.protected = e.target.checked));
  $("#sw-compare").addEventListener("change", (e) => { L.compare = e.target.checked; sync(); });
  $("#btn-sb-reset").addEventListener("click", async () => { await api("/api/sandbox/reset", { method: "POST" }); refreshSandbox(); toast("Sandbox restored to its original state."); });
  $("#btn-run").addEventListener("click", runLab);
  sync();
  renderTrace();
  refreshSandbox();

  every(async () => {
    const agents = await api("/api/agents");
    const notEnforced = agents.filter((a) => a.mode !== "enforce");
    const el = $("#lab-banner");
    if (!el) return;
    el.innerHTML = notEnforced.length ? `<div class="banner info">${icon("brain")}<div class="grow"><b>${notEnforced.map((a) => a.agent_id).join(", ")} ${notEnforced.length > 1 ? "are" : "is"} in ${esc(notEnforced[0].mode)} mode.</b><div class="muted" style="font-size:13px">Protection only observes until agents learn their normal behaviour and switch to enforce.</div></div><button class="btn primary" id="lab-setup">${icon("sparkle")}Learn &amp; enforce now</button></div>` : "";
    $("#lab-setup")?.addEventListener("click", async (e) => { try { await oneClickSetup(e.currentTarget); } catch (err) { toast(err.message, "err"); } });
  }, 4000);

  every(async () => {
    const el = $("#approval-banner");
    if (!el) return;
    const { pending } = await api("/api/approvals");
    el.innerHTML = pending.map((a) => `
      <div class="banner">${icon("hand")}<div class="grow"><b>${esc(a.agent_id)} is waiting for your approval to run <span class="mono">${esc(a.tool)}</span></b>
      <div class="muted" style="font-size:13px">${esc(a.explanation || "")}</div><div class="mono dim" style="font-size:12px;margin-top:3px">${esc(argsLine(a.args).slice(0, 160))}</div></div>
      <button class="btn danger" data-deny="${a.approval_id}">${icon("x")}Deny</button><button class="btn good" data-approve="${a.approval_id}">${icon("check")}Approve</button></div>`).join("");
    $$("[data-approve],[data-deny]", el).forEach((b) => b.addEventListener("click", async () => {
      await api(`/api/approvals/${b.dataset.approve || b.dataset.deny}`, { method: "POST", body: { approve: !!b.dataset.approve } });
      el.innerHTML = "";
    }));
  }, 1000);
};

async function refreshSandbox() {
  const el = $("#lab-sandbox");
  if (!el) return;
  const sb = await api("/api/sandbox");
  const t = sb.db.tables;
  el.innerHTML = `
    <div class="mini-list">
      <div class="r"><span class="row" style="gap:6px">${icon("db", "dim")} customers</span><b class="tnum">${t.customers ?? '<span style="color:var(--critical)">dropped</span>'}</b></div>
      <div class="r"><span>invoices</span><b class="tnum">${t.invoices ?? '<span style="color:var(--critical)">dropped</span>'}</b></div>
      <div class="r"><span>Northwind bank account</span><span class="mono" style="font-size:11.5px">${esc(sb.db.bank_accounts?.["Northwind Supplies"] || "—")}</span></div>
      <div class="r"><span>Files on share</span><b class="tnum">${sb.files.length}</b></div>
    </div>
    <div class="sep"></div>
    <span class="label-sm">${icon("mail", "dim")} Outbox (${sb.outbox.length})</span>
    <div class="mini-list">${sb.outbox.slice(-4).reverse().map((m) => `<div class="r"><span class="mono" style="font-size:12px">${esc(m.to)}</span><span class="dim" style="font-size:12px">${esc(m.subject)}</span></div>`).join("") || '<div class="dim">Empty</div>'}</div>
    <div class="sep"></div>
    <span class="label-sm">${icon("globe", "dim")} Outbound HTTP (${sb.http.length})</span>
    <div class="mini-list">${sb.http.slice(-3).reverse().map((h) => `<div class="r"><span class="mono" style="font-size:11.5px;word-break:break-all">${esc(h.url.slice(0, 70))}</span></div>`).join("") || '<div class="dim">None</div>'}</div>`;
}

function impactHtml(damage, run) {
  if (!run) return `<div class="dim">Run a scenario to see what the agent did to the company.</div>`;
  if (run.status !== "done") return `<div class="row dim"><span class="spin"></span>Running…</div>`;
  if (!damage.length) return `<div class="impact"><div class="impact-item safe">${icon("shield-check")}<div><b>No damage</b><div class="muted">Data, files, payments and the database are intact.</div></div></div></div>`;
  return `<div class="impact">${damage.map((d) => `<div class="impact-item ${d.severity}">${icon("alert")}<div><b>${esc(d.kind.replace(/_/g, " "))}</b><div class="muted">${esc(d.detail)}</div></div></div>`).join("")}</div>`;
}

function hijackRange(run) {
  const s = state.scenarios && [...state.scenarios.attacks, ...state.scenarios.benign].find((x) => x.id === run.scenario);
  if (!s || !s.hijack) return [-1, -1];
  const i = run.steps.findIndex((st) => st.ok && (st.output || "").includes(s.hijack.when_output_contains));
  return i < 0 ? [-1, -1] : [i + 1, i + s.hijack.steps.length];
}

function traceHtml(run) {
  if (!run) return "";
  const [h0, h1] = hijackRange(run);
  const steps = run.steps.map((s, i) => {
    const v = s.enforced;
    const blocked = !s.ok && (v === "DENY" || (v === "NEEDS_APPROVAL" && s.approval !== "approved"));
    const held = v === "NEEDS_APPROVAL";
    const isHijack = i >= h0 && i <= h1;
    return `<div class="trace-step ${blocked ? "blocked" : held ? "held" : ""} ${isHijack ? "hijack" : ""}">
      <div class="node">${icon(TOOL_ICON[s.tool] || "zap")}</div>
      <div class="body">
        <div class="head"><div class="row" style="gap:7px"><b>${esc(s.tool)}</b>${isHijack ? `<span class="chip deny" title="This call came from instructions hidden in content, not from the user">${icon("alert")}Injected instruction</span>` : ""}</div>
          ${run.protected ? chip(s.verdict, { mode: s.mode, approval: s.approval, simulated: s.mode === "simulate" ? s.verdict : null }) : `<span class="chip">${icon("unlock")}No check</span>`}</div>
        <div class="argline">${esc(argsLine(s.args))}</div>
        ${s.explanation ? `<div class="explain ${held ? "held" : ""}">${icon("sparkle")}<div>${esc(s.explanation)}${s.reasons?.length ? `<div style="margin-top:6px">${reasonTags(s.reasons)}</div>` : ""}</div></div>` : ""}
        <details class="out"><summary>${s.ok ? "Tool output" : "Result returned to the agent"}</summary><pre class="code">${esc(s.output)}</pre></details>
        ${s.event_id ? `<button class="btn sm ghost" style="margin-top:4px" data-ev="${s.event_id}">${icon("eye")}Decision details</button>` : ""}
      </div></div>`;
  }).join("");
  const running = run.status !== "done" && run.status !== "error";
  return `<div class="trace">${steps || ""}${running ? `<div class="row dim" style="padding:6px 0 0 46px"><span class="spin"></span>Agent is working…</div>` : ""}</div>
    ${run.status === "error" ? `<div class="banner">${icon("alert")}<div class="grow">${esc(run.error)}</div></div>` : ""}
    ${run.status === "done" ? `<div class="row dim" style="font-size:12.5px;margin-top:6px;padding-left:46px">${icon("check-circle")}${esc(run.final || "")} · ${run.seconds}s</div>` : ""}`;
}

function renderTrace() {
  const el = $("#lab-trace");
  if (!el) return;
  const { unprotected, protected: prot } = state.lab.runs;
  const head = (run, label, on) => `<div class="lane-title"><div class="row" style="gap:8px">${icon(on ? "lock" : "unlock")}<b>${label}</b></div>${run ? impactBadge(run) : ""}</div>`;
  if (!unprotected && !prot) {
    el.innerHTML = `<div class="empty" style="padding:70px 20px">${icon("lab")}<b style="color:var(--text)">Pick a scenario and press Run</b><div style="margin-top:4px">You'll see every tool call the agent makes, what AgentLeash decided, and why.</div></div>`;
    $("#lab-impact").innerHTML = impactHtml([], null);
    return;
  }
  const task = (prot || unprotected);
  const header = `<div class="card-h"><div><h2>${esc(task.name || task.task)}</h2><div class="sub">${esc(task.agent)} · user asked: “${esc(task.task)}”</div></div></div>`;
  if (unprotected && prot !== undefined && state.lab.lastCompare) {
    el.innerHTML = header + `<div class="compare"><div class="compare-col">${head(unprotected, "Without AgentLeash", false)}${traceHtml(unprotected)}</div><div class="compare-col">${head(prot, "With AgentLeash", true)}${prot ? traceHtml(prot) : '<div class="dim row"><span class="spin"></span>Waiting for the unprotected run…</div>'}</div></div>`;
  } else {
    const run = prot || unprotected;
    el.innerHTML = header + head(run, run.protected ? "With AgentLeash" : "Without AgentLeash", run.protected) + traceHtml(run);
  }
  $$("[data-ev]", el).forEach((b) => b.addEventListener("click", () => showEvent(b.dataset.ev)));
  const imp = $("#lab-impact");
  if (state.lab.lastCompare && unprotected) {
    imp.innerHTML = `<span class="label-sm">Without AgentLeash</span>${impactHtml(unprotected.damage || [], unprotected)}<div class="sep"></div><span class="label-sm">With AgentLeash</span>${impactHtml(prot?.damage || [], prot)}`;
  } else {
    const run = prot || unprotected;
    imp.innerHTML = impactHtml(run.damage || [], run);
  }
}
function impactBadge(run) {
  if (run.status !== "done") return `<span class="dim row" style="gap:6px;font-size:12px"><span class="spin"></span>running</span>`;
  return run.damage.length ? `<span class="chip deny">${icon("alert")}${run.damage.length} damage</span>` : `<span class="chip allow">${icon("shield-check")}Safe</span>`;
}

async function startRun(body) {
  let run = await api("/api/lab/run", { method: "POST", body });
  return run;
}
async function followRun(id, slot) {
  for (;;) {
    const run = await api(`/api/lab/runs/${id}`);
    state.lab.runs[slot] = run;
    if (state.page === "lab") renderTrace();
    if (run.status === "done" || run.status === "error") return run;
    await sleep(400);
  }
}

async function runLab() {
  const L = state.lab;
  if (L.running) return;
  const btn = $("#btn-run");
  L.running = true;
  btn.disabled = true;
  btn.innerHTML = `<span class="spin"></span>Running…`;
  const base = L.tab === "custom"
    ? { task: L.custom, agent: $("#custom-agent")?.value || "finance-assistant", agent_mode: "claude" }
    : { scenario_id: L.selected, agent_mode: L.agentMode };
  try {
    if (L.tab === "custom" && !L.custom.trim()) throw new Error("Type a task for the agent first.");
    L.runs = {};
    L.lastCompare = L.compare && L.tab !== "custom";
    if (L.lastCompare) {
      L.runs.protected = null;
      const u = await startRun({ ...base, protected: false });
      await followRun(u.run_id, "unprotected");
      const p = await startRun({ ...base, protected: true });
      await followRun(p.run_id, "protected");
    } else {
      const r = await startRun({ ...base, protected: L.protected });
      await followRun(r.run_id, L.protected ? "protected" : "unprotected");
    }
  } catch (e) { toast(e.message, "err"); }
  L.running = false;
  if ($("#btn-run")) { $("#btn-run").disabled = false; $("#btn-run").innerHTML = `${icon("play")}Run scenario`; }
  refreshSandbox();
}

// -------------------------------------------------------------------- feed
VIEWS.feed = async (root) => {
  const F = state.feed;
  const agents = await api("/api/agents");
  root.innerHTML = `
    <div class="card"><div class="row between">
      <div class="seg" id="feed-verdict">${[["", "All"], ["BLOCKED", "Blocked & held"], ["DENY", "Blocked"], ["NEEDS_APPROVAL", "Held"], ["ALLOW", "Allowed"]].map(([v, l]) => `<button data-v="${v}">${l}</button>`).join("")}</div>
      <div class="row"><select id="feed-agent"><option value="">All agents</option>${agents.map((a) => `<option>${esc(a.agent_id)}</option>`).join("")}</select>
      <input type="search" id="feed-q" placeholder="Search tool, task, args…" value="${esc(F.q)}"><span class="row dim" style="gap:6px;font-size:12px"><span class="dot live"></span>Live</span></div>
    </div></div>
    <div class="card flush"><div class="table-wrap" style="max-height:calc(100vh - 230px)"><table>
      <thead><tr><th>Time</th><th>Agent</th><th>Tool &amp; arguments</th><th>Decision</th><th>Anomaly</th><th>Reasons</th></tr></thead>
      <tbody id="feed-body"></tbody></table></div></div>`;
  $("#feed-agent").value = F.agent;
  const syncSeg = () => $$("#feed-verdict button").forEach((b) => b.classList.toggle("on", b.dataset.v === F.verdict));
  syncSeg();
  $$("#feed-verdict button").forEach((b) => b.addEventListener("click", () => { F.verdict = b.dataset.v; syncSeg(); load(); }));
  $("#feed-agent").addEventListener("change", (e) => { F.agent = e.target.value; load(); });
  let t;
  $("#feed-q").addEventListener("input", (e) => { F.q = e.target.value; clearTimeout(t); t = setTimeout(load, 250); });
  async function load() {
    const qs = new URLSearchParams({ limit: 300, ...(F.verdict && { verdict: F.verdict }), ...(F.agent && { agent: F.agent }), ...(F.q && { q: F.q }) });
    const rows = await api(`/api/events?${qs}`);
    const body = $("#feed-body");
    if (!body) return;
    body.innerHTML = rows.length ? rows.map((e) => `
      <tr class="clickable" data-id="${e.event_id}">
        <td class="dim tnum" style="white-space:nowrap">${clock(e.ts)}<div style="font-size:11px">${ago(e.ts)}</div></td>
        <td><span class="mono" style="font-size:12.5px">${esc(e.agent_id)}</span>${e.tainted ? `<div><span class="tag" title="Session read untrusted content">untrusted input</span></div>` : ""}</td>
        <td><b class="mono" style="font-size:12.5px">${esc(e.tool)}</b><span class="args">${esc(argsLine(e.args))}</span></td>
        <td>${chip(e.verdict, { mode: e.mode, simulated: e.simulated_verdict, approval: e.approval_status })}</td>
        <td>${e.mode === "learn" ? '<span class="dim">—</span>' : scoreBar(e.anomaly_score)}</td>
        <td style="max-width:280px">${reasonTags(e.reasons)}</td></tr>`).join("")
      : `<tr><td colspan="6"><div class="empty">${icon("feed")}No events match.</div></td></tr>`;
    $$("tr.clickable", body).forEach((r) => r.addEventListener("click", () => showEvent(r.dataset.id)));
  }
  every(load, 2500);
};

// --------------------------------------------------------------- approvals
VIEWS.approvals = async (root) => {
  root.innerHTML = `<div id="pending" class="grid cols-2"></div><div class="card flush"><div class="card-h" style="padding:16px 18px 0"><div><h2>Recent decisions</h2><div class="sub">Who approved or denied what</div></div></div><div class="table-wrap"><table><thead><tr><th>When</th><th>Agent</th><th>Action</th><th>Outcome</th><th>By</th></tr></thead><tbody id="recent"></tbody></table></div></div>`;
  every(async () => {
    const { pending, recent } = await api("/api/approvals");
    const el = $("#pending");
    if (!el) return;
    el.innerHTML = pending.length ? pending.map((a) => `
      <div class="card approval-card">
        <div class="row between"><div class="row">${chip("NEEDS_APPROVAL", { approval: "pending" })}<span class="mono">${esc(a.agent_id)}</span></div><span class="dim">${ago(a.created)}</span></div>
        <h3 class="mono" style="margin:12px 0 4px">${esc(a.tool)}</h3><div class="argline mono dim" style="font-size:12px;word-break:break-word">${esc(argsLine(a.args))}</div>
        <div class="explain held">${icon("sparkle")}<div>${esc(a.explanation || "")}<div style="margin-top:6px">${reasonTags(a.reasons)}</div></div></div>
        <dl class="kv" style="margin-top:12px"><dt>User task</dt><dd>${esc(a.task)}</dd><dt>Anomaly score</dt><dd>${scoreBar(a.anomaly_score)}</dd><dt>Untrusted input</dt><dd>${(a.taint_sources || []).map((t) => `<span class="tag">${esc(t)}</span>`).join(" ") || "none"}</dd></dl>
        <div class="actions"><button class="btn danger" data-deny="${a.approval_id}">${icon("x")}Deny</button><button class="btn good" data-approve="${a.approval_id}">${icon("check")}Approve once</button></div>
      </div>`).join("") : `<div class="card empty" style="grid-column:1/-1">${icon("check-circle")}<b style="color:var(--text)">No actions waiting.</b><div>Risky or unusual actions show up here — and in Slack, if configured.</div></div>`;
    $$("[data-approve],[data-deny]", el).forEach((b) => b.addEventListener("click", async () => {
      await api(`/api/approvals/${b.dataset.approve || b.dataset.deny}`, { method: "POST", body: { approve: !!b.dataset.approve } });
      toast(b.dataset.approve ? "Approved — the agent continues." : "Denied — the agent was told no.");
    }));
    $("#recent").innerHTML = recent.length ? recent.map((a) => `<tr><td class="dim">${ago(a.decided || a.created)}</td><td class="mono">${esc(a.agent_id)}</td><td><b class="mono">${esc(a.tool)}</b><span class="args">${esc(argsLine(a.args))}</span></td><td>${chip("NEEDS_APPROVAL", { approval: a.status })}</td><td class="dim">${esc(a.decided_by || "—")}</td></tr>`).join("") : `<tr><td colspan="5"><div class="empty">No history yet.</div></td></tr>`;
  }, 1500);
};

// ------------------------------------------------------------------ agents
VIEWS.agents = async (root) => {
  async function load() {
    const agents = await api("/api/agents");
    root.innerHTML = agents.map((a) => {
      const usedPct = a.granted ? (a.used / a.granted) * 100 : 0;
      const maxTool = Math.max(1, ...a.tools.map((t) => t.n));
      return `<div class="card agent-card" data-agent="${esc(a.agent_id)}">
        <div class="top"><div><h3>${esc(a.agent_id)}</h3><div class="muted" style="margin-top:3px">${esc(a.description)}</div>
          <div class="row" style="margin-top:8px;gap:6px">${a.policy_version ? `<span class="tag">policy v${a.policy_version} · ${esc(a.policy_source)}</span>` : '<span class="tag">no policy yet</span>'}<span class="tag">baseline: ${a.baseline.sessions} sessions</span></div></div>
          <div class="seg" data-modes>${["learn", "simulate", "enforce"].map((m) => `<button data-mode="${m}" class="${a.mode === m ? "on" : ""}">${m[0].toUpperCase() + m.slice(1)}</button>`).join("")}</div></div>
        <div class="stats">
          <div class="stat"><b class="tnum">${fmtInt(a.events)}</b><span>tool calls</span></div>
          <div class="stat"><b class="tnum">${a.denied}</b><span>blocked</span></div>
          <div class="stat"><b class="tnum">${a.held}</b><span>held for approval</span></div>
          <div class="stat"><b class="tnum">${a.granted ? Math.round(100 - usedPct) : 0}%</b><span>permissions removable</span></div>
        </div>
        <div class="grid cols-2">
          <div><span class="label-sm">Least privilege: ${a.used} of ${a.granted} granted permissions actually used</span>
            <div class="meter"><i style="width:${usedPct}%"></i></div>
            <div class="meter-legend"><span class="used">Used</span><span>Granted, never used</span></div>
            <div class="perm-chips" style="margin-top:10px">${a.used_list.map((p) => `<span class="tag used">${esc(p)}</span>`).join("")}${a.unused_list.map((p) => `<span class="tag unused" title="Granted but never used — remove it">${esc(p)}</span>`).join("")}</div></div>
          <div><span class="label-sm">Allowed tool calls by tool</span>
            ${a.tools.length ? `<div class="mini-list">${a.tools.map((t) => `<div class="r" style="border:0;padding:3px 0"><span class="mono" style="width:110px;font-size:12px">${esc(t.tool)}</span><span style="flex:1;display:flex;align-items:center"><span style="height:8px;border-radius:4px;background:var(--series-1);width:${(t.n / maxTool) * 100}%"></span></span><b class="tnum" style="width:36px;text-align:right">${t.n}</b></div>`).join("")}</div>` : '<div class="dim">No activity yet.</div>'}
          </div>
        </div>
        <div class="sep"></div>
        <div class="row between"><div class="row">
          <button class="btn" data-gen>${icon("sparkle")}Generate policy from behaviour</button>
          <button class="btn" data-replay ${a.policy_version ? "" : "disabled"}>${icon("refresh")}Replay traffic against policy</button>
          <a class="btn ghost" href="#/policies" data-open-policy>${icon("policies")}Open policy</a></div>
          <span class="dim" style="font-size:12px">${a.simulated_blocks ? `${a.simulated_blocks} calls would have been stopped in simulate mode` : ""}</span></div>
        <div data-replay-out></div>
      </div>`;
    }).join("") || `<div class="card empty">No agents connected yet.</div>`;

    $$(".agent-card").forEach((card) => {
      const id = card.dataset.agent;
      $$("[data-mode]", card).forEach((b) => b.addEventListener("click", async () => { await api(`/api/agents/${id}/mode`, { method: "POST", body: { mode: b.dataset.mode } }); toast(`${id} → ${b.dataset.mode} mode`); load(); }));
      $("[data-gen]", card).addEventListener("click", async () => {
        try { const r = await api(`/api/agents/${id}/generate-policy`, { method: "POST" }); toast(`Policy v${r.version} generated from ${r.policy.generated_from.events} observed calls.`); load(); } catch (e) { toast(e.message, "err"); }
      });
      $("[data-replay]", card).addEventListener("click", async () => {
        const r = await api(`/api/agents/${id}/replay`, { method: "POST" });
        $("[data-replay-out]", card).innerHTML = `<div class="banner info" style="margin-top:12px">${icon("refresh")}<div class="grow"><b>Replayed ${r.events} recorded calls against the current policy</b><div class="muted" style="font-size:13px">${Object.entries(r.verdicts).map(([k, v]) => `${VERDICT[k]?.label || k}: ${v}`).join(" · ")} — ${r.changed.length} decisions would change.</div></div></div>`;
      });
      $("[data-open-policy]", card).addEventListener("click", () => { state.policy.agent = id; state.policy.selected = null; });
    });
  }
  await load();
};

// ---------------------------------------------------------------- policies
function lineDiff(a, b) {
  const A = a.split("\n"), B = b.split("\n"), n = A.length, m = B.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) { out.push(["same", A[i]]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push(["del", A[i++]]);
    else out.push(["add", B[j++]]);
  }
  while (i < n) out.push(["del", A[i++]]);
  while (j < m) out.push(["add", B[j++]]);
  return out;
}

VIEWS.policies = async (root) => {
  const agents = await api("/api/agents");
  const S = state.policy;
  if (!S.agent || !agents.find((a) => a.agent_id === S.agent)) S.agent = agents[0]?.agent_id;
  root.innerHTML = `
    <div class="card"><div class="row between"><div class="row"><span class="label-sm" style="margin:0">Agent</span><select id="pol-agent">${agents.map((a) => `<option ${a.agent_id === S.agent ? "selected" : ""}>${esc(a.agent_id)}</option>`).join("")}</select><span id="pol-meta" class="dim"></span></div>
    <div class="row"><button class="btn" id="pol-sim">${icon("refresh")}Simulate draft on recorded traffic</button><button class="btn primary" id="pol-save">${icon("check")}Save as new version</button></div></div></div>
    <div class="grid split">
      <div class="card"><div class="card-h"><div><h2>Policy as code</h2><div class="sub">YAML — generated from observed behaviour, edited and reviewed like code</div></div></div>
        <div class="editor"><div class="gutter" id="gutter"></div><textarea id="pol-text" spellcheck="false" aria-label="Policy YAML"></textarea></div>
        <div id="pol-sim-out"></div></div>
      <div class="stack">
        <div class="card"><div class="card-h"><div><h3>Versions</h3><div class="sub">Click to compare with the current version</div></div></div><div id="pol-versions"></div></div>
        <div class="card"><div class="card-h"><div><h3>Changes</h3><div class="sub" id="diff-sub">Select an older version</div></div></div><div id="pol-diff" class="diff"></div></div>
        <div class="card"><div class="card-h"><h3>How rules read</h3></div><div class="mini-list muted">
          <div class="r"><span class="mono">allow / rate</span><span>tool on/off, max calls per session</span></div>
          <div class="r"><span class="mono">path.glob</span><span>folders the tool may touch</span></div>
          <div class="r"><span class="mono">to.domain_in</span><span>allowed email domains</span></div>
          <div class="r"><span class="mono">sql.readonly / ops_in</span><span>allowed SQL statements & tables</span></div>
          <div class="r"><span class="mono">sequences_deny</span><span>data-flow rules (source → sink)</span></div>
          <div class="r"><span class="mono">taint</span><span>hold risky actions after untrusted input</span></div></div></div>
      </div>
    </div>`;
  const ta = $("#pol-text");
  const gutter = () => { $("#gutter").textContent = ta.value.split("\n").map((_, i) => i + 1).join("\n"); $("#gutter").scrollTop = ta.scrollTop; };
  ta.addEventListener("input", gutter);
  ta.addEventListener("scroll", () => ($("#gutter").scrollTop = ta.scrollTop));
  ta.addEventListener("keydown", (e) => { if (e.key === "Tab") { e.preventDefault(); const s = ta.selectionStart; ta.setRangeText("  ", s, ta.selectionEnd, "end"); gutter(); } });

  async function load() {
    const { current, versions } = await api(`/api/agents/${S.agent}/policy`);
    ta.value = current ? current.yaml : "# No policy yet.\n# Put this agent in Learn mode, run normal work, then press\n# 'Generate policy from behaviour' on the Agents page.\n";
    gutter();
    $("#pol-meta").textContent = current ? `v${current.version} · ${current.source} · ${ago(current.created)}` : "";
    $("#pol-versions").innerHTML = versions.length ? versions.map((v) => `<div class="version ${S.selected === v.version ? "on" : ""}" data-v="${v.version}"><span><b>v${v.version}</b> <span class="tag">${esc(v.source)}</span></span><span class="dim" style="font-size:12px">${ago(v.created)}</span></div>`).join("") : '<div class="dim">No versions yet.</div>';
    $$(".version").forEach((el) => el.addEventListener("click", () => { S.selected = +el.dataset.v; showDiff(versions); $$(".version").forEach((x) => x.classList.toggle("on", x === el)); }));
    showDiff(versions);
  }
  function showDiff(versions) {
    const cur = versions[0], old = versions.find((v) => v.version === S.selected);
    if (!cur || !old || old === cur) { $("#pol-diff").innerHTML = '<div class="dim" style="padding:10px">—</div>'; $("#diff-sub").textContent = "Select an older version"; return; }
    $("#diff-sub").textContent = `v${old.version} → v${cur.version}`;
    $("#pol-diff").innerHTML = lineDiff(old.yaml, cur.yaml).filter(([k]) => k !== "same").map(([k, l]) => `<div class="${k}">${esc(l)}</div>`).join("") || '<div class="dim" style="padding:10px">Identical</div>';
  }
  $("#pol-agent").addEventListener("change", (e) => { S.agent = e.target.value; S.selected = null; load(); });
  $("#pol-save").addEventListener("click", async () => {
    try { const r = await api(`/api/agents/${S.agent}/policy`, { method: "PUT", body: { yaml: ta.value } }); toast(`Saved policy v${r.version}.`); load(); } catch (e) { toast(e.message, "err"); }
  });
  $("#pol-sim").addEventListener("click", async () => {
    try {
      const r = await api(`/api/agents/${S.agent}/replay`, { method: "POST", body: { yaml: ta.value } });
      $("#pol-sim-out").innerHTML = `<div class="banner info" style="margin-top:12px">${icon("refresh")}<div class="grow"><b>Draft replayed on ${r.events} recorded calls — nothing was enforced</b>
        <div class="muted" style="font-size:13px">${Object.entries(r.verdicts).map(([k, v]) => `${VERDICT[k]?.label || k}: ${v}`).join(" · ")} · ${r.changed.length} decisions differ from what happened</div>
        ${r.changed.slice(-6).map((c) => `<div class="mono" style="font-size:12px;margin-top:4px">${esc(c.tool)} — ${esc(VERDICT[c.was]?.label || c.was)} → ${esc(VERDICT[c.now]?.label || c.now)} <span class="dim">${esc((c.task || "").slice(0, 60))}</span></div>`).join("")}</div></div>`;
    } catch (e) { toast(e.message, "err"); }
  });
  await load();
};

// -------------------------------------------------------------------- eval
VIEWS.eval = async (root) => {
  topActions(`<button class="btn primary" id="eval-run">${icon("play")}Run benchmark</button>`);
  root.innerHTML = `<div id="eval-progress"></div><div id="eval-body" class="stack" style="gap:18px"></div>`;
  $("#eval-run").addEventListener("click", async () => {
    try { await api("/api/eval/run", { method: "POST", body: { use_llm: false } }); poll(); } catch (e) { toast(e.message, "err"); }
  });
  let lastGen = null;
  async function poll() {
    const { job, results } = await api("/api/eval");
    const prog = $("#eval-progress");
    if (!prog) return;
    prog.innerHTML = job.status === "running" ? `<div class="card"><div class="row between"><b>Running benchmark…</b><span class="dim">${esc(job.message || "")}</span></div><div class="progress" style="margin-top:10px"><i style="width:${(job.progress || 0) * 100}%"></i></div></div>` : "";
    $("#eval-run").disabled = job.status === "running";
    if (results && results.generated !== lastGen) { lastGen = results.generated; renderEval(results); }
    if (!results && job.status !== "running") $("#eval-body").innerHTML = `<div class="card empty" style="padding:60px">${icon("eval")}<b style="color:var(--text)">No benchmark results yet</b><div style="margin-top:4px">The benchmark learns from ${"normal"} work, then replays held-out tasks and 15 attacks with no defence, a static policy only, and full AgentLeash.</div></div>`;
    if (job.status === "running") setTimeout(poll, 700);
  }
  poll();
};

function renderEval(r) {
  const S = r.setups, order = ["unprotected", "policy_only", "full"];
  const full = S.full, none = S.unprotected;
  $("#eval-body").innerHTML = `
    <div class="grid cols-3">
      <div class="card kpi glow"><div class="label">${icon("shield-check")}Attacks stopped by AgentLeash</div><div class="big-num tnum">${full.attacks_total - full.attacks_succeeded}<small> / ${full.attacks_total}</small></div><div class="foot">${none.attacks_succeeded} of ${none.attacks_total} succeed with no defence</div></div>
      <div class="card kpi"><div class="label">${icon("check-circle")}Legitimate tasks completed</div><div class="big-num tnum">${full.benign_completed}<small> / ${full.benign_total}</small></div><div class="foot">${pct(full.benign_approval_rate)} needed a human approval</div></div>
      <div class="card kpi"><div class="label">${icon("clock")}Decision latency</div><div class="big-num tnum">${full.latency_p50_ms ?? "—"}<small> ms p50</small></div><div class="foot">p95 ${full.latency_p95_ms ?? "—"} ms · ${r.llm ? "with Claude scoping" : "rules + heuristics, no LLM"}</div></div>
    </div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><div><h2>Attack success rate</h2><div class="sub">Share of ${full.attacks_total} attacks that caused real damage — lower is better</div></div></div><div id="ch-attack"></div></div>
      <div class="card"><div class="card-h"><div><h2>Legitimate work completed</h2><div class="sub">Held-out normal tasks that finished — higher is better</div></div></div><div id="ch-benign"></div></div>
    </div>
    <div class="card"><div class="card-h"><div><h2>Anomaly score by call</h2><div class="sub">Every tool call in the full-AgentLeash run. Attack calls cluster above the thresholds; normal work stays low.</div></div>
      <div class="legend"><span><i style="background:var(--series-1)"></i>Normal tasks</span><span><i style="background:var(--series-2)"></i>Attack runs</span></div></div><div class="chart-wrap" id="ch-strip"></div></div>
    <div class="card flush"><div class="card-h" style="padding:16px 18px 0"><div><h2>Scenario results</h2><div class="sub">Learned from ${r.train_scenarios} training tasks × ${r.learn_repeats} · finished in ${r.seconds}s</div></div></div>
      <div class="table-wrap"><table class="matrix"><thead><tr><th>Scenario</th><th>Agent</th>${order.map((k) => `<th class="c" style="text-align:center">${esc(S[k].label)}</th>`).join("")}</tr></thead><tbody>
      ${S.full.rows.map((row, i) => `<tr><td><span class="tag">${esc(row.id)}</span> ${esc(row.name)}${row.kind === "attack" ? ` <span class="dim" style="font-size:12px">· ${esc(row.category)}</span>` : ""}</td><td class="mono dim" style="font-size:12px">${esc(row.agent)}</td>
        ${order.map((k) => cell(S[k].rows[i])).join("")}</tr>`).join("")}
      </tbody></table></div></div>`;
  const items = (key, total) => order.map((k) => ({ label: S[k].label, value: S[k][key], text: `${Math.round(S[k][key] * 100)}%  (${key === "attack_success_rate" ? S[k].attacks_succeeded + "/" + S[k].attacks_total : S[k].benign_completed + "/" + S[k].benign_total})` }));
  hbars($("#ch-attack"), items("attack_success_rate"), { max: 1 });
  hbars($("#ch-benign"), items("benign_completion_rate"), { max: 1 });
  stripPlot($("#ch-strip"), r.anomaly_points, [{ v: state.config.thresholds.approval, label: "Held", color: cssVar("--warning") }, { v: state.config.thresholds.deny, label: "Blocked", color: cssVar("--critical") }]);
}
function cell(row) {
  if (row.kind === "attack") {
    return row.attack_succeeded
      ? `<td class="c"><span class="res bad" title="${esc(row.damage.map((d) => d.detail).join("; "))}">${icon("alert")}Damage</span></td>`
      : `<td class="c"><span class="res ok">${icon("shield-check")}Stopped</span></td>`;
  }
  if (row.completed) return `<td class="c"><span class="res ${row.needed_approval ? "held" : "ok"}">${icon(row.needed_approval ? "hand" : "check-circle")}${row.needed_approval ? "Done after approval" : "Completed"}</span></td>`;
  const why = row.steps.filter((s) => !s.ok).map((s) => `${s.tool}: ${(s.reasons || []).join(", ")}`).join("; ");
  return `<td class="c"><span class="res bad" title="${esc(why)}">${icon("x")}Blocked</span></td>`;
}

// ------------------------------------------------------------------- audit
VIEWS.audit = async (root) => {
  topActions(`<button class="btn" id="audit-verify">${icon("shield-check")}Verify chain</button><button class="btn danger" id="audit-tamper">${icon("alert")}Simulate tampering</button>`);
  root.innerHTML = `<div class="card" id="chain"></div><div class="card flush"><div class="table-wrap" style="max-height:calc(100vh - 330px)"><table><thead><tr><th>#</th><th>Time</th><th>Event</th><th>Details</th><th>Hash</th></tr></thead><tbody id="audit-body"></tbody></table></div></div>`;
  async function load() {
    const { verify, rows } = await api("/api/audit");
    $("#chain").innerHTML = `<div class="chain-ok"><div class="shield ${verify.ok ? "ok" : "bad"}">${icon(verify.ok ? "shield-check" : "shield-x")}</div>
      <div><h2 style="margin:0;font-size:17px">${verify.ok ? "Audit chain intact" : "Tampering detected"}</h2>
      <div class="muted">${verify.ok ? `${fmtInt(verify.rows)} entries · each one hashes the one before it, so editing any entry breaks every hash after it.` : esc(verify.detail)}</div>
      ${verify.ok && verify.head ? `<div class="hash" style="margin-top:4px">head ${esc(verify.head.slice(0, 32))}…</div>` : ""}</div></div>`;
    $("#audit-body").innerHTML = rows.map((r) => {
      const p = r.payload;
      const detail = r.kind === "decision" ? `${chip(p.verdict, { simulated: p.simulated_verdict })} <span class="mono" style="font-size:12px">${esc(p.agent_id)} → ${esc(p.tool)}</span> ${p.tampered ? '<span class="tag" style="color:var(--critical)">edited</span>' : ""}` : `<span class="mono" style="font-size:12px">${esc(JSON.stringify(p))}</span>`;
      return `<tr class="${!verify.ok && r.seq >= verify.broken_at ? "broken" : ""}"><td class="tnum dim">${r.seq}</td><td class="dim" style="white-space:nowrap">${clock(r.ts)}</td><td><span class="tag">${esc(r.kind)}</span></td><td>${detail}</td><td class="hash">${esc(r.hash.slice(0, 16))}…</td></tr>`;
    }).join("") || `<tr><td colspan="5"><div class="empty">The audit log is empty.</div></td></tr>`;
  }
  $("#audit-verify").addEventListener("click", async () => { await load(); toast("Chain re-verified."); });
  $("#audit-tamper").addEventListener("click", async () => {
    if (!confirm("Rewrite one blocked decision as 'allowed' directly in the database, like an attacker covering their tracks?")) return;
    try { await api("/api/audit/tamper", { method: "POST" }); toast("One entry was silently edited. See what verification says.", "err"); load(); } catch (e) { toast(e.message, "err"); }
  });
  every(load, 4000);
};

// -------------------------------------------------------------------- boot
function applyThemeIcon() {
  const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  $("#theme-toggle").innerHTML = icon(dark ? "sun" : "moon");
}
$("#theme-toggle").addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme === "dark";
  document.documentElement.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("al-theme", document.documentElement.dataset.theme); } catch (e) {}
  applyThemeIcon();
  route();
});

let resizeT;
addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => { if (["overview", "eval"].includes(state.page)) route(); }, 300); });
addEventListener("hashchange", route);

(async function boot() {
  applyThemeIcon();
  try { state.config = await api("/api/config"); } catch (e) { state.config = { llm: false, thresholds: { approval: 0.6, deny: 0.9 } }; }
  await pollGlobal();
  setInterval(pollGlobal, 3000);
  route();
})();
