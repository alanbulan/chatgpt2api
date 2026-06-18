from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from main import app


if os.getenv("VERCEL"):
    @asynccontextmanager
    async def _vercel_lifespan(_: FastAPI):
        yield

    app.router.lifespan_context = _vercel_lifespan

    # Persist editable runtime config in the app_state table when DATABASE_URL is
    # configured. Fall back to /tmp so Vercel never writes to the read-only bundle.
    from services.config import config
    from services.state_service import state_service

    saved_config = state_service.load("config")
    if saved_config:
        config.data.update(saved_config)

    def _vercel_config_save() -> None:
        if state_service.save("config", config.data):
            return
        fallback = Path(os.getenv("CHATGPT2API_DATA_DIR", "/tmp/chatgpt2api/data")) / "config.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(json.dumps(config.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    config._save = _vercel_config_save  # type: ignore[method-assign]
