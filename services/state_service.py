from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import Column, String, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class AppStateModel(Base):
    __tablename__ = "app_state"

    key = Column(String(255), primary_key=True)
    data = Column(Text, nullable=False)


class StateService:
    """Small JSON state store for Vercel/runtime settings.

    It is intentionally independent from services.config to avoid circular imports.
    When STORAGE_BACKEND is database-like and DATABASE_URL is available, state is
    persisted in PostgreSQL/SQL through the app_state table. Otherwise callers can
    fall back to their file-based behavior.
    """

    def __init__(self) -> None:
        self._engine = None
        self._Session = None
        self._disabled = False

    @staticmethod
    def _enabled() -> bool:
        backend = os.getenv("STORAGE_BACKEND", "").strip().lower()
        return backend in {"postgres", "postgresql", "mysql", "database", "sqlite"} and bool(
            os.getenv("DATABASE_URL", "").strip()
        )

    def _session_factory(self):
        if self._disabled or not self._enabled():
            return None
        if self._Session is not None:
            return self._Session
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            return None
        try:
            self._engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=300)
            Base.metadata.create_all(self._engine)
            self._Session = sessionmaker(bind=self._engine)
            return self._Session
        except Exception:
            self._disabled = True
            return None

    def load(self, key: str) -> dict[str, Any]:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return {}
        factory = self._session_factory()
        if factory is None:
            return {}
        session = factory()
        try:
            row = session.get(AppStateModel, normalized_key)
            if row is None:
                return {}
            try:
                payload = json.loads(row.data)
            except Exception:
                return {}
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
        finally:
            session.close()

    def save(self, key: str, value: dict[str, Any]) -> bool:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return False
        factory = self._session_factory()
        if factory is None:
            return False
        session = factory()
        try:
            payload = json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False)
            row = session.get(AppStateModel, normalized_key)
            if row is None:
                session.add(AppStateModel(key=normalized_key, data=payload))
            else:
                row.data = payload
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def health(self) -> dict[str, object]:
        factory = self._session_factory()
        if factory is None:
            return {"enabled": False, "status": "disabled"}
        session = factory()
        try:
            session.execute(text("SELECT 1"))
            return {"enabled": True, "status": "healthy"}
        except Exception as exc:
            return {"enabled": True, "status": "unhealthy", "error": str(exc)}
        finally:
            session.close()


state_service = StateService()
