from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from main import app


if os.getenv("VERCEL"):
    @asynccontextmanager
    async def _vercel_lifespan(_: FastAPI):
        yield

    app.router.lifespan_context = _vercel_lifespan
