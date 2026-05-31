/**
 * KhetiBadi — Frontend JS
 * Talks to the Python proxy only. No Google URLs here.
 *
 * ── CONFIG ──────────────────────────────────────────────────────────────────
 * Replace this with your actual Render URL.
 * This is the ONLY URL in the frontend. Everything else is hidden server-side.
 */
const API_BASE = "https://YOUR-RENDER-APP.onrender.com";

// ── State ─────────────────────────────────────────────────────────────────────
let authToken    = localStorage.getItem("kb_token");
let currentUser  = localStorage.getItem("kb_user");
let displayName  = localStorage.getItem("kb_display");
let selectedFile = null;
let allExpenses  = [];

// ── Boot ──────────────────────────────────────────────────────────────────────
(async function init() {
  if (authToken) {
    try {
      await api("/api/config");
      showApp();
      await loadConfig();
      return;
    } catch { clearAuth(); }
  }
  showLogin();
})();

// ── API wrapper ───────────────────────────────────────────────────────────────
async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(authToken ? { "Authorization": "Bearer " + authToken } : {}),
  };
  const res  = await fetch(API_BASE + path, { ...options, headers });
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data;
}

// ── Auth ──────────────────────────────────────────────────────────────────────
function showLogin() {
  document.getElementById("login-page").style.display = "flex";
  document.getElementById("app-page").style.display   = "none";
}

function showApp() {
  document.getElementById("login-page").style.display = "none";
  document.getElementById("app-page").style.display   = "block";
  document.getElementById("user-display").textContent = displayName || currentUser;
  setTodayDate();
}

function clearAuth() {
  authToken = currentUser = displayName = null;
  ["kb_token", "kb_user", "kb_display"].forEach(k => localStorage.removeItem(k));
}

document.getElementById("login-pass").addEventListener("keydown", e => {
  if (e.key === "Enter") doLogin();
});

async function doLogin() {
  const btn      = document.getElementById("login-btn");
  const err      = document.getElementById("login-error");
  const username = document.getElementById("login-user").value.trim().toLowerCase();
  const password = document.getElementById("login-pass").value;
  err.style.display = "none";

  if (!username || !password) {
    err.textContent = "Please enter both username and password.";
    err.style.display = "block";
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Signing in…';

  try {
    const data = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    authToken   = data.token;
    currentUser = data.username;
    displayName = data.display_name;
    localStorage.setItem("kb_token",   authToken);
    localStorage.setItem("kb_user",    currentUser);
    localStorage.setItem("kb_display", displayName);
    showApp();
    await loadConfig();
  } catch (e) {
    err.textContent = e.message;
    err.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Sign In";
  }
}

async function doLogout() {
  try { await api("/api/logout", { method: "POST" }); } catch {}
  clearAuth();
  showLogin();
}

// ── Config (dropdowns) ────────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const data = await api("/api/config");
    fillSelect("f-category", data.categories);
    fillSelect("f-payment",  data.payment_modes);
  } catch (e) {
    console.error("Config load failed:", e);
  }
}

function fillSelect(id, items) {
  const sel   = document.getElementById(id);
  const first = sel.options[0];
  sel.innerHTML = "";
  sel.appendChild(first);
  items.forEach(item => {
    const opt = document.createElement("option");
    opt.value = item; opt.textContent = item;
    sel.appendChild(opt);
  });
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t, i) => {
    t.classList.toggle("active", (i === 0 && name === "add") || (i === 1 && name === "records"));
  });
  document.getElementById("tab-add").classList.toggle("active",     name === "add");
  document.getElementById("tab-records").classList.toggle("active", name === "records");
  if (name === "records") loadRecords();
}

// ── Form ──────────────────────────────────────────────────────────────────────
function setTodayDate() {
  document.getElementById("f-date").value = new Date().toISOString().split("T")[0];
}

function handleFileSelect(input) {
  selectedFile = input.files[0] || null;
  const preview = document.getElementById("file-preview");
  const nameEl  = document.getElementById("file-name-display");
  if (selectedFile) {
    nameEl.textContent   = `${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`;
    preview.style.display = "flex";
  } else {
    preview.style.display = "none";
  }
}

// Drag-and-drop
const uploadZone = document.getElementById("upload-zone");
uploadZone.addEventListener("dragover",  e => { e.preventDefault(); uploadZone.classList.add("drag-over"); });
uploadZone.addEventListener("dragleave", ()  => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", e => {
  e.preventDefault();
  uploadZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) {
    document.getElementById("f-screenshot").files = e.dataTransfer.files;
    handleFileSelect(document.getElementById("f-screenshot"));
  }
});

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(reader.result.split(",")[1]);
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

// ── Submit expense ────────────────────────────────────────────────────────────
async function submitExpense() {
  const btn = document.getElementById("submit-btn");
  const err = document.getElementById("submit-error");
  const suc = document.getElementById("submit-success");
  err.style.display = "none";
  suc.style.display = "none";

  const payload = {
    date:          document.getElementById("f-date").value,
    farm_location: document.getElementById("f-location").value.trim(),
    category:      document.getElementById("f-category").value,
    amount:        document.getElementById("f-amount").value,
    vendor:        document.getElementById("f-vendor").value.trim(),
    payment_mode:  document.getElementById("f-payment").value,
    notes:         document.getElementById("f-notes").value.trim(),
    screenshot_name: selectedFile ? selectedFile.name : null,
  };

  // Client-side pre-check (business layer also validates server-side)
  const missing = ["date","farm_location","category","amount","vendor","payment_mode"]
    .filter(k => !payload[k]);
  if (missing.length) {
    err.textContent   = "Please fill in all required fields.";
    err.style.display = "block";
    return;
  }

  if (selectedFile) {
    if (selectedFile.size > 5 * 1024 * 1024) {
      err.textContent   = "Photo is too large (max 5 MB).";
      err.style.display = "block";
      return;
    }
    try {
      payload.screenshot_base64 = await readFileAsBase64(selectedFile);
    } catch {
      err.textContent   = "Could not read the photo. Please try again.";
      err.style.display = "block";
      return;
    }
  }

  btn.disabled  = true;
  btn.innerHTML = `<span class="spinner"></span>${selectedFile ? "Uploading & saving…" : "Submitting…"}`;

  try {
    const data = await api("/api/submit", { method: "POST", body: JSON.stringify(payload) });
    suc.style.display = "flex";
    if (data.photo_url && data.photo_url !== "No photo") {
      const link       = document.createElement("a");
      link.href        = data.photo_url;
      link.target      = "_blank";
      link.textContent = " View uploaded photo →";
      link.style.marginLeft = "8px";
      suc.appendChild(link);
    }
    resetForm();
  } catch (e) {
    err.textContent   = e.message;
    err.style.display = "block";
  } finally {
    btn.disabled  = false;
    btn.innerHTML = "Submit Expense";
  }
}

function resetForm() {
  ["f-date","f-amount","f-vendor","f-notes","f-location"].forEach(id => {
    document.getElementById(id).value = id === "f-date" ? new Date().toISOString().split("T")[0] : "";
  });
  ["f-category","f-payment"].forEach(id => {
    document.getElementById(id).selectedIndex = 0;
  });
  document.getElementById("f-screenshot").value = "";
  document.getElementById("file-preview").style.display = "none";
  selectedFile = null;
}

// ── Records ───────────────────────────────────────────────────────────────────
// Filtering is now done server-side by the business layer.
// The frontend just sends the period and date range as query params.

async function loadRecords() {
  const tbody = document.getElementById("records-body");
  tbody.innerHTML = `<tr><td colspan="8" class="no-data"><span class="no-data-icon">⏳</span>Loading…</td></tr>`;

  const period   = document.getElementById("filter-period").value;
  const dateFrom = document.getElementById("filter-from").value;
  const dateTo   = document.getElementById("filter-to").value;

  let url = `/api/expenses?period=${period}`;
  if (dateFrom) url += `&from=${dateFrom}`;
  if (dateTo)   url += `&to=${dateTo}`;

  try {
    const data    = await api(url);
    allExpenses   = data.expenses || [];
    const summary = data.summary  || {};
    const total   = data.total    || 0;

    if (!allExpenses.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="no-data"><span class="no-data-icon">📭</span>No expenses for this period</td></tr>`;
    } else {
      renderTable(allExpenses);
    }

    renderSummary(summary);

    document.getElementById("filter-count").textContent =
      `${allExpenses.length} of ${total} entries`;

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" class="no-data" style="color:var(--red)">⚠️ ${e.message}</td></tr>`;
  }
}

function applyFilter() {
  const period  = document.getElementById("filter-period").value;
  const custom  = document.getElementById("custom-range");
  custom.classList.toggle("visible", period === "custom");
  loadRecords();
}

function renderTable(rows) {
  const tbody = document.getElementById("records-body");
  tbody.innerHTML = rows.map(r => {
    const photoCell = r.photo_url && r.photo_url.startsWith("http")
      ? `<a href="${r.photo_url}" target="_blank" style="color:var(--green);font-weight:600;text-decoration:none">📷 View</a>`
      : `<span style="color:var(--muted)">—</span>`;
    return `
    <tr>
      <td>${r.date || "—"}</td>
      <td>${r.paid_by || "—"}</td>
      <td><span class="category-badge">${r.category || "—"}</span></td>
      <td class="amount-cell">₹${Number(r.amount || 0).toLocaleString("en-IN")}</td>
      <td>${r.vendor || "—"}</td>
      <td>${r.payment_mode || "—"}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.notes||""}">${r.notes || "—"}</td>
      <td>${photoCell}</td>
    </tr>`;
  }).join("");
}

function renderSummary(s) {
  document.getElementById("summary-bar").innerHTML = `
    <div class="summary-card">
      <div class="label">Total Spent</div>
      <div class="value">₹${Number(s.total || 0).toLocaleString("en-IN")}<small> filtered</small></div>
    </div>
    <div class="summary-card">
      <div class="label">Today</div>
      <div class="value green">₹${Number(s.today_total || 0).toLocaleString("en-IN")}<small> today</small></div>
    </div>
    <div class="summary-card">
      <div class="label">Entries</div>
      <div class="value">${s.entry_count || 0}<small> records</small></div>
    </div>
    ${s.top_category ? `
    <div class="summary-card">
      <div class="label">Top Category</div>
      <div class="value" style="font-size:1.1rem;padding-top:0.3rem">${s.top_category}<br>
        <small>₹${Number(s.top_amount || 0).toLocaleString("en-IN")}</small>
      </div>
    </div>` : ""}
  `;
}
