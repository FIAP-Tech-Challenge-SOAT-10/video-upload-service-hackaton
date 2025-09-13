# app/middleware/observability.py
import time, uuid, logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import set_request_context
from app.core.metrics import REQUESTS, LATENCY

log = logging.getLogger("http")

def _path_template(request: Request) -> str:
    # usa o template (ex: /videos/{id_video}) para evitar cardinalidade alta
    try:
        return request.scope.get("route").path  # type: ignore[attr-defined]
    except Exception:
        return request.url.path

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        # (Opcional) quando Auth estiver plugado: extrair user_id do JWT
        user_id = None

        set_request_context(rid, user_id)
        start = time.perf_counter()
        path_tmpl = _path_template(request)

        try:
            response: Response = await call_next(request)
            status = response.status_code
            return response
        finally:
            dur = (time.perf_counter() - start) * 1000.0
            method = request.method
            status = locals().get("status", 500)

            # métricas
            REQUESTS.labels(path=path_tmpl, method=method, status=str(status)).inc()
            LATENCY.labels(path=path_tmpl, method=method).observe(dur / 1000.0)

            # log de acesso
            log.info(
                f"{method} {path_tmpl} -> {status} in {dur:.1f}ms",
                extra={
                    "path": path_tmpl,
                    "method": method,
                    "status": status,
                    "duration_ms": round(dur, 1),
                },
            )
