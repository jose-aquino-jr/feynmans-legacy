"""Logging estruturado em JSON, sem dependências externas."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

_EXTRA_FIELDS = (
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "dataset",
    "model",
)


class JsonFormatter(logging.Formatter):
    """Formata registros de log como uma linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


_HANDLER_MARKER = "_feynmans_legacy_api_handler"


def configure_logging(level: str = "INFO") -> None:
    """Configura o logger raiz com saída JSON, idempotentemente."""
    root = logging.getLogger()
    root.setLevel(level)

    for handler in root.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            handler.setFormatter(JsonFormatter())
            return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    root.addHandler(handler)
