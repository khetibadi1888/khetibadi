// ═══════════════════════════════════════════════════════════════════════════════
//  KhetiBadi — Google Apps Script backend
//  Paste this into: Google Sheet → Extensions → Apps Script
//  No changes needed here — all business logic lives in the Python layer.
// ═══════════════════════════════════════════════════════════════════════════════

const CONFIG = {
  users: [
    { username: "badal",  passwordHash: hashPassword("jayguru@1234"), displayName: "Badal Kumar Sahu" },
    { username: "shree",  passwordHash: hashPassword("shree@1234"),   displayName: "Shree" },
  ],
  categories:    ["Seeds","Fertilizer","Pesticide","Labour","Fuel","Equipment Rent","Irrigation","Repair","Transport","Other"],
  locations:     ["North Farm","South Farm","Main Field","Greenhouse","Storage"],
  payment_modes: ["Cash","UPI","Bank Transfer","Cheque","Other"],
  driveFolderName: "Farm Expense Photos",
  sheetName:       "Expenses",
  sessionHours:    12,
};

const HEADERS = ["Timestamp","Submitted By","Date","Paid By","Category","Amount (₹)","Vendor","Payment Mode","Notes","Photo URL"];

function doGet(e)  { return handleRequest(e); }
function doPost(e) { return handleRequest(e); }

function handleRequest(e) {
  try {
    const action = (e.parameter && e.parameter.action) || "";
    const body   = parseBody(e);
    switch (action) {
      case "login":    return respond(handleLogin(body));
      case "logout":   return respond(handleLogout(body));
      case "config":   return respond(handleConfig(body));
      case "submit":   return respond(handleSubmit(body));
      case "expenses": return respond(handleExpenses(body));
      default:         return respond({ error: "Unknown action" }, 400);
    }
  } catch (err) {
    return respond({ error: err.message }, 500);
  }
}

function parseBody(e) {
  if (e.postData && e.postData.contents) {
    try { return JSON.parse(e.postData.contents); } catch { return {}; }
  }
  return e.parameter || {};
}

function respond(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

// ── Auth ──────────────────────────────────────────────────────────────────────
function hashPassword(password) {
  const raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, password, Utilities.Charset.UTF_8);
  return raw.map(b => ('0' + (b & 0xFF).toString(16)).slice(-2)).join('');
}

function generateToken() {
  return Utilities.getUuid().replace(/-/g,'') + Utilities.getUuid().replace(/-/g,'');
}

function saveSession(token, username, displayName) {
  const props  = PropertiesService.getScriptProperties();
  const expiry = new Date();
  expiry.setHours(expiry.getHours() + CONFIG.sessionHours);
  props.setProperty("session_" + token, JSON.stringify({ username, displayName, expiry: expiry.toISOString() }));
}

function getSession(token) {
  if (!token) return null;
  const raw = PropertiesService.getScriptProperties().getProperty("session_" + token);
  if (!raw) return null;
  const session = JSON.parse(raw);
  if (new Date() > new Date(session.expiry)) {
    PropertiesService.getScriptProperties().deleteProperty("session_" + token);
    return null;
  }
  return session;
}

function deleteSession(token) {
  PropertiesService.getScriptProperties().deleteProperty("session_" + token);
}

function requireAuth(body) {
  const session = getSession(body.token || "");
  if (!session) throw new Error("Unauthorized — please log in again");
  return session;
}

// ── Handlers ──────────────────────────────────────────────────────────────────
function handleLogin(body) {
  const username = (body.username || "").trim().toLowerCase();
  const password = body.password || "";
  if (!username || !password) return { error: "Username and password required" };
  const hash = hashPassword(password);
  const user = CONFIG.users.find(u => u.username === username && u.passwordHash === hash);
  if (!user) return { error: "Invalid username or password" };
  const token = generateToken();
  saveSession(token, user.username, user.displayName);
  return { token, username: user.username, display_name: user.displayName };
}

function handleLogout(body) {
  if (body.token) deleteSession(body.token);
  return { message: "Logged out" };
}

function handleConfig(body) {
  requireAuth(body);
  return { categories: CONFIG.categories, locations: CONFIG.locations, payment_modes: CONFIG.payment_modes };
}

function handleSubmit(body) {
  const session = requireAuth(body);
  const required = ["date","farm_location","category","amount","vendor","payment_mode"];
  for (const f of required) { if (!body[f]) return { error: "Missing field: " + f }; }

  let photoUrl = "No photo";
  if (body.screenshot_base64 && body.screenshot_name) {
    try { photoUrl = uploadPhotoToDrive(body.screenshot_base64, body.screenshot_name, session.username, body.date); }
    catch (err) { photoUrl = "Upload failed: " + err.message; }
  }

  const sheet = getOrCreateSheet();
  const ts    = Utilities.formatDate(new Date(), "UTC", "yyyy-MM-dd HH:mm:ss") + " UTC";
  sheet.appendRow([ts, session.username, body.date, body.farm_location, body.category, Number(body.amount), body.vendor, body.payment_mode, body.notes || "", photoUrl]);
  return { message: "Expense recorded successfully!", photo_url: photoUrl };
}

function handleExpenses(body) {
  requireAuth(body);
  const sheet = getOrCreateSheet();
  const data  = sheet.getDataRange().getValues();
  if (data.length <= 1) return { expenses: [] };
  const headers = data[0];
  const rows = data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = row[i]; });
    return obj;
  }).reverse();
  return { expenses: rows };
}

// ── Sheet helper ──────────────────────────────────────────────────────────────
function getOrCreateSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(CONFIG.sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.sheetName);
    sheet.appendRow(HEADERS);
    const header = sheet.getRange(1, 1, 1, HEADERS.length);
    header.setBackground("#2C1A0E").setFontColor("#F2D98B").setFontWeight("bold");
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 170);
    sheet.setColumnWidth(10, 250);
  }
  return sheet;
}

// ── Drive helper ──────────────────────────────────────────────────────────────
function getOrCreateDriveFolder() {
  const results = DriveApp.getFoldersByName(CONFIG.driveFolderName);
  if (results.hasNext()) return results.next();
  return DriveApp.createFolder(CONFIG.driveFolderName);
}

function uploadPhotoToDrive(base64Data, originalName, username, date) {
  const decoded  = Utilities.base64Decode(base64Data);
  const mimeType = guessMimeType(originalName);
  const ext      = originalName.includes(".") ? originalName.split(".").pop() : "jpg";
  const ts       = Utilities.formatDate(new Date(), "UTC", "yyyyMMdd_HHmmss");
  const filename = username + "_" + date + "_" + ts + "." + ext;
  const blob     = Utilities.newBlob(decoded, mimeType, filename);
  const folder   = getOrCreateDriveFolder();
  const file     = folder.createFile(blob);
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return file.getUrl();
}

function guessMimeType(filename) {
  const ext = (filename.split(".").pop() || "").toLowerCase();
  return { jpg:"image/jpeg", jpeg:"image/jpeg", png:"image/png", gif:"image/gif", webp:"image/webp", pdf:"application/pdf", heic:"image/heic" }[ext] || "image/jpeg";
}
