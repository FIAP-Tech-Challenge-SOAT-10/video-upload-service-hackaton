# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import settings
from app.core import auth as core_auth
from app.infrastructure.clients.auth_client import AuthClient
from app.routers import videos as videos_router

from fastapi import APIRouter

# opcional
try:
    from app.core.logging import setup_logging
except Exception:
    def setup_logging():
        pass

try:
    from app.middleware.observability import ObservabilityMiddleware
except Exception:
    ObservabilityMiddleware = None

try:
    from app.routers import health as health_router
except Exception:
    health_router = None

# Prometheus (fallback simples)
USE_INLINE_METRICS = False
try:
    from app.core.metrics import router_metrics
except Exception:
    router_metrics = None
    USE_INLINE_METRICS = True
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, REGISTRY


router_debug = APIRouter(prefix="/debug", tags=["debug"])

@router_debug.get("/auth-status")
async def auth_status():
    client = getattr(core_auth, "_auth_client", None)
    info = {
        "initialized": client is not None,
        "base_url": getattr(client, "_base_url", None),
        "timeout": getattr(client, "_timeout", None),
        "cache_ttl": getattr(client, "_cache_ttl", None),
    }
    return info



@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    setup_logging()

    # inicializa e injeta no módulo core_auth
    client = AuthClient(
        base_url=settings.auth_base_url,
        timeout_seconds=settings.auth_timeout_seconds,
        cache_ttl=settings.auth_cache_ttl_seconds,
    )
    core_auth.auth_client = client
    app.state.auth_client = client   # só se quiser acessar via request.app.state

    try:
        yield
    finally:
        if core_auth.auth_client:
            await core_auth.auth_client.aclose()
        core_auth.auth_client = None


# --- App ---
app = FastAPI(
    title="Video Service",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Observabilidade (opcional)
if ObservabilityMiddleware:
    app.add_middleware(ObservabilityMiddleware)

# Routers
app.include_router(videos_router.router)
app.include_router(router_debug)
if health_router:
    app.include_router(health_router.router)
else:
    @app.get("/health")
    def health():
        return {"status": "ok"}

# /metrics
if router_metrics:
    app.include_router(router_metrics)
elif USE_INLINE_METRICS:
    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

