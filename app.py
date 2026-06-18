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

    # Vercel's function bundle is read-only. Keep all mutable runtime files in
    # /tmp, and persist editable settings in PostgreSQL when DATABASE_URL exists.
    runtime_data_dir = Path(os.getenv("CHATGPT2API_DATA_DIR", "/tmp/chatgpt2api/data"))
    runtime_data_dir.mkdir(parents=True, exist_ok=True)

    import services.config as config_module

    config_module.DATA_DIR = runtime_data_dir
    config_module.BACKUP_STATE_FILE = runtime_data_dir / "backup_state.json"

    from services.config import config
    from services.state_service import state_service

    saved_config = state_service.load("config")
    if saved_config:
        config.data.update(saved_config)

    def _vercel_config_save() -> None:
        if state_service.save("config", config.data):
            return
        fallback = runtime_data_dir / "config.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(json.dumps(config.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    config._save = _vercel_config_save  # type: ignore[method-assign]

    try:
        import services.log_service as log_module

        log_module.log_service.path = runtime_data_dir / "logs.jsonl"
        log_module.log_service.path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        import services.image_storage_service as image_storage_module

        image_storage_module.IMAGE_INDEX_FILE = runtime_data_dir / "image_index.json"
        image_storage_module.image_storage_service.index_file = image_storage_module.IMAGE_INDEX_FILE
    except Exception:
        pass

    try:
        import services.image_tags_service as image_tags_module

        image_tags_module.TAGS_FILE = runtime_data_dir / "image_tags.json"
    except Exception:
        pass

    try:
        import services.backup_service as backup_module

        backup_module.DATA_DIR = runtime_data_dir
    except Exception:
        pass
