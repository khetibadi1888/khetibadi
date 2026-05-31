"""
KhetiBadi — Expense service
All business rules live here.
No HTTP, no Flask, no Google API calls — pure Python logic.

Future growth ideas (add here, not in proxy):
  - Budget limits per category
  - GST calculation
  - Multi-farm aggregation
  - Monthly report generation
  - Anomaly detection (unusually large expense)
  - WhatsApp / SMS notification triggers
"""

from datetime import date, datetime, timedelta
from typing import Optional
from .models import Expense, Summary

# ── Validation ────────────────────────────────────────────────────────────────

REQUIRED_FIELDS = ["date", "farm_location", "category", "amount", "vendor", "payment_mode"]
MAX_PHOTO_BYTES = 5 * 1024 * 1024   # 5 MB
MAX_AMOUNT      = 10_000_000        # 1 crore sanity cap


def validate_expense(data: dict) -> list[str]:
    """
    Validate raw input dict. Returns a list of error strings.
    Empty list means valid.
    """
    errors = []

    for field in REQUIRED_FIELDS:
        if not data.get(field):
            errors.append(f"'{field}' is required")

    if data.get("amount"):
        try:
            amt = float(data["amount"])
            if amt <= 0:
                errors.append("Amount must be greater than 0")
            if amt > MAX_AMOUNT:
                errors.append(f"Amount seems too large (max ₹{MAX_AMOUNT:,})")
        except (ValueError, TypeError):
            errors.append("Amount must be a valid number")

    if data.get("date"):
        try:
            datetime.strptime(data["date"], "%Y-%m-%d")
        except ValueError:
            errors.append("Date must be in YYYY-MM-DD format")

    if data.get("screenshot_base64"):
        # Rough byte size estimate from base64 length
        estimated_bytes = len(data["screenshot_base64"]) * 3 // 4
        if estimated_bytes > MAX_PHOTO_BYTES:
            errors.append("Photo is too large (max 5 MB)")

    return errors


# ── Filtering ─────────────────────────────────────────────────────────────────

def parse_date(val) -> Optional[date]:
    """Robustly parse a date value from various formats."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(val).split("T")[0].strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def filter_by_period(expenses: list[Expense], period: str,
                     date_from: Optional[str] = None,
                     date_to:   Optional[str] = None) -> list[Expense]:
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
        start = today.replace(day=1)
        # last day of this month
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)

    elif period == "last_month":
        first_this = today.replace(day=1)
        end   = first_this - timedelta(days=1)
        start = end.replace(day=1)

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


# ── Summary calculation ───────────────────────────────────────────────────────

def calculate_summary(expenses: list[Expense]) -> Summary:
    """
    Calculate summary stats for a list of expenses.
    Used for the summary cards on the Records tab.
    """
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
    Normalises date format here so JS never needs to parse ISO timestamps.
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
