"""Vercel's entry point for hosted mode (R-50). Vercel runs `app` for every request (vercel.json).

Set these in the Vercel project's environment variables (docs/deploying.md):
CODECOMPASS_MODE=hosted, CODECOMPASS_DATABASE_URL, CODECOMPASS_SECRET_KEY,
CODECOMPASS_GITHUB_CLIENT_ID, and CODECOMPASS_GITHUB_CLIENT_SECRET.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("CODECOMPASS_MODE", "hosted")

from codecompass import create_app  # noqa: E402

app = create_app()
