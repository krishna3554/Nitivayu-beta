"""Test bootstrap: required env defaults before any app import.

The suite runs without live infrastructure (DB-free FakeSession pattern),
but Settings() still requires DATABASE_URL/JWT_SECRET at import time.
Defaults apply only when the environment does not already provide values.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.setdefault("ALLOW_DEV_OTP", "true")
