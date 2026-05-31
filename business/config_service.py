"""
KhetiBadi — Config Service
===========================
Loads business/config.json — categories, locations, payment modes,
validation rules, and app settings.

Users and passwords are NOT here. They live in Code.gs (Apps Script)
which is private to your Google account and never in GitHub.

Data engineers edit config.json and push to change anything here.
"""

import json
import os
from typing import Optional

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_raw() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class ConfigService:
    def __init__(self):
        self._config: dict = {}
        self.load()

    def load(self) -> None:
        self._config = _load_raw()

    def reload(self) -> None:
        """Hot-reload config without restarting the server."""
        self.load()

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def categories(self) -> list[str]:
        return list(self._config.get("categories", []))

    @property
    def locations(self) -> list[str]:
        return list(self._config.get("locations", []))

    @property
    def payment_modes(self) -> list[str]:
        return list(self._config.get("payment_modes", []))

    @property
    def validation_rules(self) -> dict:
        return dict(self._config.get("validation_rules", {}))

    @property
    def session_duration_hours(self) -> int:
        return int(self._config.get("session", {}).get("duration_hours", 12))

    @property
    def drive_folder_name(self) -> str:
        return self._config.get("app", {}).get("drive_folder_name", "Farm Expense Photos")

    @property
    def sheet_name(self) -> str:
        return self._config.get("app", {}).get("sheet_name", "Expenses")

    @property
    def max_amount(self) -> float:
        return float(self.validation_rules.get("max_amount", 1_000_000))

    @property
    def max_photo_size_bytes(self) -> int:
        return int(self.validation_rules.get("max_photo_size_mb", 5)) * 1024 * 1024

    @property
    def allowed_photo_types(self) -> list[str]:
        return list(self.validation_rules.get("allowed_photo_types", ["jpg", "jpeg", "png", "pdf"]))

    @property
    def required_fields(self) -> list[str]:
        return list(self.validation_rules.get("required_fields", []))

    def is_valid_category(self, category: str) -> bool:
        return category in self.categories

    def is_valid_payment_mode(self, mode: str) -> bool:
        return mode in self.payment_modes

    def frontend_config(self) -> dict:
        """Only what the frontend needs — no sensitive data."""
        return {
            "categories":    self.categories,
            "locations":     self.locations,
            "payment_modes": self.payment_modes,
        }

    def summary(self) -> dict:
        """For data engineers — full config summary."""
        return {
            "categories":       self.categories,
            "locations":        self.locations,
            "payment_modes":    self.payment_modes,
            "validation_rules": self.validation_rules,
            "session_hours":    self.session_duration_hours,
            "app":              self._config.get("app", {}),
        }


# Singleton
config_service = ConfigService()
