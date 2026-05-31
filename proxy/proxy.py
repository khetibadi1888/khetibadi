"""
KhetiBahi — Proxy server
========================
Thin HTTP layer only. No business logic here.
All rules, validation, and data formatting live in the business/ package.

Env vars (set on Render):
  APPS_SCRIPT_URL   — Apps Script Web App exec URL  (secret)
  PROXY_SECRET      — random string for token entropy
  ALLOWED_ORIGINS   — your GitHub Pages URL
  PORT              — set automatically by Render
"""

import os
import sys
import json
from functools import wraps

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Add parent dir to path so we can import business/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from business import (
    auth_service,
    validate_expense,
    filter_by_period,
    calculate_summary,
    format_expenses_for_frontend,
    Expense,
)

load_dotenv()

app = Flask(__name__)
CORS(app, origins=os.getenv("ALLOWED_ORIGINS", "*"), supports_credentials=True)

APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "")


# ── Apps Script caller ────────────────────────────────────────────────────────

def call_gas(action: str, body: dict, timeout: int = 60) -> dict:
    """POST to Apps Script. Raises ValueError on app-level errors."""
    if not APPS_SCRIPT_URL:
        raise RuntimeError("APPS_SCRIPT_URL is not configured on this server.")
    resp = requests.post(
        APPS_SCRIPT_URL + "?action=" + action,
        data=json.dumps(body),
        headers={"Content-Type": "text/plain"},
        allow_redirects=True,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(data["error"])
    return data


# ── Auth decorator ────────────────────────────────────────────────────────────

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token   = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        session = auth_service.get_session(token)
        if not session:
            return jsonify({"error": "Unauthorized — please log in again"}), 401
        request.session = session
        return f(*args, **kwargs)
    return decorated


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/login", methods=["POST"])
def login():
    body     = request.get_json(force=True) or {}
    username = body.get("username", "").strip().lower()
    password = body.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Verify credentials with Apps Script
    try:
        gas_result = call_gas("login", {"username": username, "password": password})
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": f"Could not reach backend: {e}"}), 502

    # Create proxy session — GAS token stored server-side only
    proxy_token = auth_service.create_session(
        username     = gas_result["username"],
        display_name = gas_result["display_name"],
        gas_token    = gas_result["token"],
    )

    return jsonify({
        "token":        proxy_token,
        "username":     gas_result["username"],
        "display_name": gas_result["display_name"],
    })


@app.route("/api/logout", methods=["POST"])
@require_auth
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    auth_service.delete_session(token)
    return jsonify({"message": "Logged out"})


@app.route("/api/config", methods=["GET"])
@require_auth
def config():
    session = request.session
    # Cache config in session to save a round-trip on every page load
    if "cached_config" in session:
        return jsonify(session["cached_config"])
    try:
        result = call_gas("config", {"token": auth_service.get_gas_token(session)})
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    session["cached_config"] = result
    return jsonify(result)


@app.route("/api/submit", methods=["POST"])
@require_auth
def submit():
    session = request.session
    body    = request.get_json(force=True) or {}

    # ── Business layer: validate ──────────────────────────────────────────────
    errors = validate_expense(body)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    gas_payload = {
        "token":             auth_service.get_gas_token(session),
        "date":              body["date"],
        "farm_location":     body["farm_location"],
        "category":          body["category"],
        "amount":            float(body["amount"]),
        "vendor":            body["vendor"],
        "payment_mode":      body["payment_mode"],
        "notes":             body.get("notes", ""),
        "screenshot_name":   body.get("screenshot_name"),
        "screenshot_base64": body.get("screenshot_base64"),
    }

    try:
        result = call_gas("submit", gas_payload, timeout=90)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({
        "message":   result.get("message", "Expense recorded!"),
        "photo_url": result.get("photo_url", ""),
    })


@app.route("/api/expenses", methods=["GET"])
@require_auth
def expenses():
    session = request.session

    # Query params for filtering (passed from frontend)
    period    = request.args.get("period", "all")
    date_from = request.args.get("from")
    date_to   = request.args.get("to")

    try:
        result = call_gas("expenses", {"token": auth_service.get_gas_token(session)})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    # ── Business layer: parse, filter, summarise ──────────────────────────────
    raw_expenses = [Expense.from_sheet_row(r) for r in result.get("expenses", [])]

    filtered  = filter_by_period(raw_expenses, period, date_from, date_to)
    summary   = calculate_summary(filtered)
    formatted = format_expenses_for_frontend(filtered)

    return jsonify({
        "expenses": formatted,
        "summary":  summary.to_dict(),
        "total":    len(raw_expenses),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
