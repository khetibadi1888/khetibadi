"""
KhetiBadi — Data models
Single source of truth for all data shapes.
Add fields here when the app grows (e.g. GST number, crop type, farm ID).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Expense:
    date:          str            # ISO date string "YYYY-MM-DD"
    farm_location: str            # "Paid By" person name
    category:      str
    amount:        float
    vendor:        str
    payment_mode:  str
    notes:         str  = ""
    photo_url:     str  = "No photo"
    submitted_by:  str  = ""
    timestamp:     str  = ""

    def to_row(self) -> list:
        """Return a flat list matching the Google Sheet column order."""
        return [
            self.timestamp,
            self.submitted_by,
            self.date,
            self.farm_location,
            self.category,
            self.amount,
            self.vendor,
            self.payment_mode,
            self.notes,
            self.photo_url,
        ]

    @classmethod
    def from_sheet_row(cls, row: dict) -> "Expense":
        """Build an Expense from a Google Sheet record dict."""
        return cls(
            timestamp     = str(row.get("Timestamp", "")),
            submitted_by  = str(row.get("Submitted By", "")),
            date          = str(row.get("Date", "")).split("T")[0],  # strip ISO time
            farm_location = str(row.get("Paid By", row.get("Farm Location", ""))),
            category      = str(row.get("Category", "")),
            amount        = float(str(row.get("Amount (₹)", 0) or 0)),
            vendor        = str(row.get("Vendor", "")),
            payment_mode  = str(row.get("Payment Mode", "")),
            notes         = str(row.get("Notes", "")),
            photo_url     = str(row.get("Photo URL", "No photo")),
        )

    def to_dict(self) -> dict:
        return {
            "timestamp":     self.timestamp,
            "submitted_by":  self.submitted_by,
            "date":          self.date,
            "paid_by":       self.farm_location,
            "category":      self.category,
            "amount":        self.amount,
            "vendor":        self.vendor,
            "payment_mode":  self.payment_mode,
            "notes":         self.notes,
            "photo_url":     self.photo_url,
        }


@dataclass
class Summary:
    total:        float
    today_total:  float
    entry_count:  int
    top_category: Optional[str]
    top_amount:   Optional[float]

    def to_dict(self) -> dict:
        return {
            "total":        self.total,
            "today_total":  self.today_total,
            "entry_count":  self.entry_count,
            "top_category": self.top_category,
            "top_amount":   self.top_amount,
        }
