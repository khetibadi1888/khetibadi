"""
KhetiBadi — Expense Service
============================
All business rules live here. No HTTP, no Flask, no Google API calls.

Validation rules come from config_service (config.json) — not hardcoded.
Data engineers can change limits, required fields, and allowed photo types
by editing config.json and pushing — no code change needed.

Future growth (add functions here, not in proxy.py):
  - Budget limits per category
  - GST calculation
  - Anomaly detection
  - Monthly report generation
  - WhatsApp / SMS alert triggers
"""

from datetime import date, datetime, timedelta
from typing import Optional

from .models import Expense, Summary
from .config_service import config_service


# ── Validation ────────────────────────────────────────────────────────────────

def validate_expense(data: dict) -> list[str]:
    """
    Validate a raw expense dict against rules in config.json.
    Returns a list of error strings. Empty list = valid.

    Rules come from config.json validation_rules section:
      - required_fields
      - max_amount
      - max_photo_size_mb
      - allowed_photo_types
    """
    errors  = []
    rules   = config_service.validation_rules

    # Required fields
    for field in config_service.required_fields:
        if not data.get(field):
            label = field.replace("_", " ").title()
            errors.append(f"{label} is required")

    # Amount validation
    if data.get("amount"):
        try:
            amt = float(data["amount"])
            if amt <= 0:
                errors.append("Amount must be greater than 0")
            if amt > config_service.max_amount:
                errors.append(f"Amount seems too large (max ₹{config_service.max_amount:,.0f})")
        except (ValueError, TypeError):
            errors.append("Amount must be a valid number")

    # Date format
    if data.get("date"):
        try:
            datetime.strptime(data["date"], "%Y-%m-%d")
        except ValueError:
            errors.append("Date must be in YYYY-MM-DD format")

    # Category must be in allowed list
    if data.get("category") and not config_service.is_valid_category(data["category"]):
        errors.append(
            f"'{data['category']}' is not a valid category. "
            f"Allowed: {', '.join(config_service.categories)}"
        )

    # Payment mode must be in allowed list
    if data.get("payment_mode") and not config_service.is_valid_payment_mode(data["payment_mode"]):
        errors.append(
            f"'{data['payment_mode']}' is not a valid payment mode. "
            f"Allowed: {', '.join(config_service.payment_modes)}"
        )

    # Photo size check
    if data.get("screenshot_base64"):
        estimated_bytes = len(data["screenshot_base64"]) * 3 // 4
        if estimated_bytes > config_service.max_photo_size_bytes:
            mb = config_service.max_photo_size_bytes // (1024 * 1024)
            errors.append(f"Photo is too large (max {mb} MB)")

    # Photo type check
    if data.get("screenshot_name"):
        ext = data["screenshot_name"].rsplit(".", 1)[-1].lower() if "." in data["screenshot_name"] else ""
        if ext and ext not in config_service.allowed_photo_types:
            errors.append(
                f"'{ext}' is not an allowed photo type. "
                f"Allowed: {', '.join(config_service.allowed_photo_types)}"
            )

    return errors


# ── Filtering ─────────────────────────────────────────────────────────────────

def parse_date(val) -> Optional[date]:
    """Robustly parse a date from any format."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(val).split("T")[0].strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def filter_by_period(
    expenses:  list[Expense],
    period:    str,
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
) -> list[Expense]:
    """
    Filter expenses by time period.
    period: "all" | "this_week" | "last_week" | "this_month" | "last_month" | "custom"
    """
    today = date.today()

    if period == "all":
        return expenses

    if period == "this_week":
        start = today - timedelta(days=today.weekday())
        end   = start + timedelta(days=6)

    elif period == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        end   = start + timedelta(days=6)

    elif period == "this_month":
        start      = today.replace(day=1)
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        end        = next_month - timedelta(days=1)

    elif period == "last_month":
        first_this = today.replace(day=1)
        end        = first_this - timedelta(days=1)
        start      = end.replace(day=1)

    elif period == "custom":
        start = parse_date(date_from)
        end   = parse_date(date_to)
        if not start and not end:
            return expenses
    else:
        return expenses

    result = []
    for exp in expenses:
        d = parse_date(exp.date)
        if not d:
            result.append(exp)
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        result.append(exp)
    return result


# ── Summary ───────────────────────────────────────────────────────────────────

def calculate_summary(expenses: list[Expense]) -> Summary:
    """Calculate summary stats for the Records tab summary cards."""
    today = date.today()
    total = sum(e.amount for e in expenses)

    today_total = sum(
        e.amount for e in expenses
        if parse_date(e.date) == today
    )

    category_totals: dict[str, float] = {}
    for e in expenses:
        cat = e.category or "Other"
        category_totals[cat] = category_totals.get(cat, 0) + e.amount

    top_entry = max(category_totals.items(), key=lambda x: x[1]) if category_totals else None

    return Summary(
        total        = round(total, 2),
        today_total  = round(today_total, 2),
        entry_count  = len(expenses),
        top_category = top_entry[0] if top_entry else None,
        top_amount   = round(top_entry[1], 2) if top_entry else None,
    )


# ── Formatting ────────────────────────────────────────────────────────────────

def format_expenses_for_frontend(expenses: list[Expense]) -> list[dict]:
    """
    Convert Expense objects to clean dicts for the frontend.
    Normalises date to '30 May 2026' so JS never needs to parse ISO strings.
    """
    result = []
    for e in expenses:
        d = parse_date(e.date)
        result.append({
            "date":         d.strftime("%d %b %Y") if d else e.date,
            "paid_by":      e.farm_location,
            "category":     e.category,
            "amount":       e.amount,
            "vendor":       e.vendor,
            "payment_mode": e.payment_mode,
            "notes":        e.notes,
            "photo_url":    e.photo_url,
            "submitted_by": e.submitted_by,
        })
    return result
