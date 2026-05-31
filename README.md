# 🌾 KhetiBadi — Farm Expense Tracker

## Architecture

```
Browser (GitHub Pages)
        │  HTTPS + Bearer token
        ▼
Python Proxy (Render)          ← only URL the browser knows
        │
        ├── business/
        │     ├── models.py          ← Expense dataclass
        │     ├── auth_service.py    ← sessions & tokens
        │     └── expense_service.py ← validation, filters, summaries
        │
        │  server-to-server (hidden)
        ▼
Apps Script Web App
        │
        ├── Google Sheet   ← expense rows
        └── Google Drive   ← receipt photos
```

**What the browser never sees:** Apps Script URL, Sheet ID, Drive folder, any Google credentials.

---

## One-time Setup (do this once, then GitHub Actions handles everything)

### Step 1 — Google Sheet + Apps Script

1. Create a new Google Sheet at https://sheets.google.com — name it **Farm Expenses**
2. Inside the sheet: **Extensions → Apps Script**
3. Delete default code, paste entire contents of **`Code.gs`**
4. Edit the `CONFIG.users` block with your actual usernames and passwords
5. **Save** (Ctrl+S)
6. **Deploy → New deployment**
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
7. Click **Deploy** → authorize when prompted
8. Copy the **Web App URL** — keep it secret

---

### Step 2 — Render (one-time setup)

1. Go to https://render.com → **New → Web Service**
2. Connect your GitHub repo
3. Render will detect `render.yaml` automatically
4. Set these **Environment Variables** in the Render dashboard:

   | Key | Value |
   |-----|-------|
   | `APPS_SCRIPT_URL` | Web App URL from Step 1 |
   | `ALLOWED_ORIGINS` | `https://YOUR-USERNAME.github.io` |

5. Deploy — copy your Render URL (e.g. `https://khetibadi-proxy.onrender.com`)

---

### Step 3 — GitHub Secrets (3 secrets total)

Go to your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|-------------|-------|
| `RENDER_URL` | Your Render URL e.g. `https://khetibadi-proxy.onrender.com` |
| `RENDER_DEPLOY_HOOK` | Render → your service → Settings → **Deploy Hook** → copy URL |
| (no third secret needed) | |

---

### Step 4 — Enable GitHub Pages

1. GitHub repo → **Settings → Pages**
2. Source: **GitHub Actions**
3. That's it — the workflow handles deployment

---

### Step 5 — Push and go

```bash
git add .
git commit -m "initial deploy"
git push origin main
```

GitHub Actions will:
1. Inject your Render URL into `app.js`
2. Deploy `frontend/` → GitHub Pages
3. Trigger Render to redeploy the proxy
4. Run a health check smoke test

Your app will be live at: `https://YOUR-USERNAME.github.io/khetibadi`

---

## Every deploy after that

Just push to `main`:

```bash
git add .
git commit -m "your change"
git push
```

GitHub Actions deploys everything automatically.

---

## Project structure

```
khetibadi/
├── .github/
│   └── workflows/
│       └── deploy.yml        ← CI/CD pipeline
├── frontend/
│   ├── index.html            ← HTML shell (~175 lines)
│   ├── style.css             ← all CSS
│   └── app.js                ← all JS
├── business/
│   ├── __init__.py
│   ├── models.py             ← Expense + Summary dataclasses
│   ├── auth_service.py       ← session management
│   └── expense_service.py    ← validation, filtering, summaries
├── proxy/
│   ├── proxy.py              ← Flask HTTP layer only
│   ├── requirements.txt
│   └── Procfile
├── Code.gs                   ← paste into Apps Script
├── render.yaml               ← Render build config
├── .env.example              ← local dev reference
└── .gitignore
```

## Local development

```bash
cd proxy
cp ../.env.example .env
# fill in your APPS_SCRIPT_URL in .env

pip install -r requirements.txt
python proxy.py
```

Then open `frontend/index.html` in a browser — change `API_BASE` in `app.js` to `http://localhost:5000` temporarily.

---

## Adding a new user

Edit `Code.gs` in Apps Script → update `CONFIG.users` → **Deploy → Manage deployments → Edit → New version → Deploy**.

No changes needed in Python or the frontend.

## Future growth ideas (add to `business/expense_service.py`)

- Monthly budget limits per category → alert if exceeded
- GST calculation on amounts
- Export to PDF report
- Multi-farm filtering
- WhatsApp notification on large expenses
- Anomaly detection (flag unusually large entries)
