"use strict";

// All text from the API is inserted with textContent / createElement, never direct HTML injection,
// so a record containing markup or script is displayed as plain text.

const $ = (id) => document.getElementById(id);
const STAGE_ORDER = ["Discovery", "Qualification", "Proposal", "Negotiation"];

const state = { opps: [], accounts: [], summary: null, sortKey: "close_date", sortDir: 1, timer: null };

function el(tag, opts = {}, ...children) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text !== undefined) node.textContent = opts.text;
  if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, v);
  for (const c of children) node.append(c);
  return node;
}

async function api(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error("request failed");
  const body = await res.json();
  if (body.status !== "ok") throw new Error("request failed");
  return body.data;
}

function showError(message) {
  const box = $("error");
  box.textContent = message;
  box.hidden = !message;
}

// ---- dates -------------------------------------------------------------------

function daysUntil(iso) {
  if (!iso) return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  const today = new Date();
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((Date.UTC(y, m - 1, d) - start) / 86400000);
}

function relative(days) {
  if (days === null) return "";
  if (days === 0) return "today";
  if (days > 0) return `in ${days} day${days === 1 ? "" : "s"}`;
  return `${-days} day${days === -1 ? "" : "s"} ago`;
}

// ---- rendering ---------------------------------------------------------------

function renderKpis() {
  const s = state.summary;
  $("kpi-accounts").textContent = s.total_accounts;
  $("kpi-opps").textContent = s.total_opportunities;
  $("kpi-stages").textContent = Object.keys(s.by_stage).length;
  const n = s.next_to_close;
  if (n) {
    $("kpi-next-name").textContent = n.name;
    const d = daysUntil(n.close_date);
    $("kpi-next-meta").textContent = `${n.account_name} · ${n.close_date} (${relative(d)})`;
    $("next-card").classList.toggle("soon", d !== null && d <= 30);
  } else {
    $("kpi-next-name").textContent = "No dated deals";
    $("kpi-next-meta").textContent = "";
  }
}

function renderStageChart() {
  const box = $("stage-chart");
  box.replaceChildren();
  const by = state.summary.by_stage;
  const stages = [...STAGE_ORDER.filter((s) => s in by), ...Object.keys(by).filter((s) => !STAGE_ORDER.includes(s))];
  const max = Math.max(1, ...Object.values(by));
  for (const stage of stages) {
    const fill = el("div", { class: "bar-fill" });
    fill.style.width = `${(by[stage] / max) * 100}%`;
    box.append(el("div", { class: "stage-row" },
      el("span", { text: stage }),
      el("div", { class: "bar-track" }, fill),
      el("span", { class: "stage-count", text: String(by[stage]) }),
    ));
  }
}

function renderAccounts() {
  const box = $("accounts");
  box.replaceChildren();
  const active = $("f-account").value;
  for (const a of state.accounts) {
    const btn = el("button", {
      class: "account" + (a.account_id === active ? " active" : ""),
      attrs: { type: "button", "aria-pressed": String(a.account_id === active) },
    },
      el("span", {}, 
        el("span", { class: "account-name", text: a.name || "Unnamed" }),
        el("br"),
        el("span", { class: "account-meta", text: [a.industry, a.region].filter(Boolean).join(" · ") || "No details" }),
      ),
      el("span", { class: "pill", text: `${a.opportunity_count} opp${a.opportunity_count === 1 ? "" : "s"}` }),
    );
    btn.addEventListener("click", () => {
      $("f-account").value = a.account_id === $("f-account").value ? "" : a.account_id;
      refreshOpps();
    });
    box.append(btn);
  }
}

function fillSelects() {
  const stageSel = $("f-stage");
  const accSel = $("f-account");
  const keepStage = stageSel.value;
  const keepAcc = accSel.value;
  stageSel.replaceChildren(el("option", { text: "All stages", attrs: { value: "" } }));
  for (const s of Object.keys(state.summary.by_stage)) stageSel.append(el("option", { text: s, attrs: { value: s } }));
  accSel.replaceChildren(el("option", { text: "All accounts", attrs: { value: "" } }));
  for (const a of state.accounts) accSel.append(el("option", { text: a.name || a.account_id, attrs: { value: a.account_id } }));
  stageSel.value = keepStage;
  accSel.value = keepAcc;
}

function compare(a, b) {
  const k = state.sortKey;
  const av = a[k], bv = b[k];
  // Unknown (null) values always sort last, whichever direction is chosen.
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  return String(av).localeCompare(String(bv), undefined, { sensitivity: "base" }) * state.sortDir;
}

function renderTable() {
  const rows = [...state.opps].sort(compare);
  const body = $("opps-body");
  body.replaceChildren();
  $("empty").hidden = rows.length > 0;
  $("result-count").textContent = `(${rows.length})`;

  for (const o of rows) {
    const days = daysUntil(o.close_date);
    let dateCell;
    if (o.close_date) {
      const cls = days !== null && days < 0 ? "date-sub past" : days !== null && days <= 30 ? "date-sub soon" : "date-sub";
      dateCell = el("td", {}, el("span", { text: o.close_date }), el("span", { class: cls, text: relative(days) }));
    } else {
      dateCell = el("td", {}, el("span", { class: "unknown", text: "Unknown" }));
    }
    body.append(el("tr", {},
      el("td", { text: o.name || "Unnamed" }),
      el("td", { text: o.account_name || "Unknown" }),
      el("td", {}, el("span", { class: `tag tag-${(o.stage || "").replace(/[^A-Za-z]/g, "")}`, text: o.stage || "Unknown" })),
      dateCell,
      el("td", { class: o.owner ? "" : "muted", text: o.owner || "Unknown" }),
    ));
  }

  for (const th of document.querySelectorAll("th[data-sort]")) {
    th.setAttribute("aria-sort", th.dataset.sort === state.sortKey ? (state.sortDir === 1 ? "ascending" : "descending") : "none");
  }
}

// ---- data --------------------------------------------------------------------

async function refreshOpps() {
  const params = new URLSearchParams();
  const q = $("f-q").value.trim();
  if (q) params.set("q", q);
  if ($("f-stage").value) params.set("stage", $("f-stage").value);
  if ($("f-account").value) params.set("account", $("f-account").value);
  try {
    state.opps = (await api(`/api/opportunities?${params}`)).opportunities;
    showError("");
    renderTable();
    renderAccounts();
  } catch {
    showError("Could not load opportunities. Is the dashboard server still running?");
  }
}

async function loadAll() {
  try {
    const [summary, accounts] = await Promise.all([api("/api/summary"), api("/api/accounts")]);
    state.summary = summary;
    state.accounts = accounts.accounts;
    fillSelects();
    renderKpis();
    renderStageChart();
    await refreshOpps();
  } catch {
    showError("Could not load the CRM data. Start the dashboard with: uv run mock-crm-web");
  }
}

// ---- events ------------------------------------------------------------------

$("f-q").addEventListener("input", () => {
  clearTimeout(state.timer);
  state.timer = setTimeout(refreshOpps, 200);
});
$("f-stage").addEventListener("change", refreshOpps);
$("f-account").addEventListener("change", refreshOpps);
$("f-reset").addEventListener("click", () => {
  $("f-q").value = "";
  $("f-stage").value = "";
  $("f-account").value = "";
  refreshOpps();
});

for (const th of document.querySelectorAll("th[data-sort]")) {
  th.tabIndex = 0;
  const activate = () => {
    state.sortDir = state.sortKey === th.dataset.sort ? -state.sortDir : 1;
    state.sortKey = th.dataset.sort;
    renderTable();
  };
  th.addEventListener("click", activate);
  th.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); }
  });
}

for (const btn of document.querySelectorAll(".nav-item")) {
  btn.addEventListener("click", () => {
    for (const b of document.querySelectorAll(".nav-item")) b.classList.remove("active");
    btn.classList.add("active");
  });
}

loadAll();
// Pick up changes to the data files (the server re-reads them on every request).
setInterval(loadAll, 30000);
