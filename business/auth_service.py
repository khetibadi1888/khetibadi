"""
KhetiBadi — Auth service
Handles proxy-level sessions. The browser gets a proxy token;
the Apps Script token is stored server-side only and never sent to the browser.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

SESSION_HOURS     = 12
GAS_SESSION_HOURS = 11   # refresh 1 h before proxy session expires


class AuthService:
    def __init__(self):
        # proxy_token → session dict
        self._sessions: dict[str, dict] = {}

    # ── Public interface ──────────────────────────────────────────────────────

    def create_session(
        self,
        username:     str,
        display_name: str,
        gas_token:    str,
    ) -> str:
        """
        Create a proxy session after a successful login.
        Returns the proxy token to give to the browser.
        The gas_token is stored server-side only.
        """
        proxy_token = secrets.token_hex(32)
        now         = datetime.now(timezone.utc)
        self._sessions[proxy_token] = {
            "username":         username,
            "display_name":     display_name,
            "expires":          now + timedelta(hours=SESSION_HOURS),
            "gas_token":        gas_token,
            "gas_token_expiry": now + timedelta(hours=GAS_SESSION_HOURS),
        }
        return proxy_token

    def get_session(self, proxy_token: str) -> Optional[dict]:
        """
        Return the session for this token, or None if missing/expired.
        Automatically cleans up expired sessions.
        """
        if not proxy_token:
            return None
        session = self._sessions.get(proxy_token)
        if not session:
            return None
        if datetime.now(timezone.utc) > session["expires"]:
            self._sessions.pop(proxy_token, None)
            return None
        return session

    def delete_session(self, proxy_token: str) -> None:
        self._sessions.pop(proxy_token, None)

    def get_gas_token(self, session: dict) -> str:
        """
        Return the Apps Script token stored in this session.
        Never expose this to the browser — only call from proxy routes.
        """
        return session.get("gas_token", "")

    def is_valid(self, proxy_token: str) -> bool:
        return self.get_session(proxy_token) is not None

    def purge_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        now     = datetime.now(timezone.utc)
        expired = [t for t, s in self._sessions.items() if now > s["expires"]]
        for t in expired:
            del self._sessions[t]
        return len(expired)


# Singleton — shared across all requests in this process
auth_service = AuthService()
