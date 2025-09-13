# app/core/logging.py
import logging, json, sys, contextvars
from datetime import datetime

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("req_id", default=None)
_user_id:    contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)

def set_request_context(request_id: str | None = None, user_id: str | None = None):
    if request_id is not None: _request_id.set(request_id)
    if user_id is not None: _user_id.set(user_id)

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": _request_id.get(),
            "user_id": _user_id.get(),
        }
        # anexar extras usuais se existirem
        for k in ("path", "method", "status", "duration_ms", "size_bytes"):
            v = getattr(record, k, None)
            if v is not None: payload[k] = v
        return json.dumps(payload, ensure_ascii=False)

def setup_logging():
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # abaixa o ruído de libs
    for noisy in ("uvicorn.error", "uvicorn.access", "botocore", "boto3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
