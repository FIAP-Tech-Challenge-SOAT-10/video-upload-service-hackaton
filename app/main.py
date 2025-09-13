# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

# --- Logging (opcional: se você criou app/core/logging.py) ---
try:
    from app.core.logging import setup_logging
except Exception:
    def setup_logging():
        # no-op se o módulo não existir
        pass

# --- Observabilidade (opcional: se você criou app/middleware/observability.py) ---
try:
    from app.middleware.observability import ObservabilityMiddleware
except Exception:
    ObservabilityMiddleware = None  # fallback

# --- Repositório e Routers ---
from app.routers import videos as videos_router
try:
    from app.routers import health as health_router  # opcional, se você tiver um router de health
except Exception:
    health_router = None

try:
    from app.infrastructure.repositories.video_repo import VideoRepo
except Exception:
    VideoRepo = None  # fallback para não quebrar em dev sem infra

# --- Prometheus (/metrics): tenta usar router pronto; se não houver, cria a rota aqui ---
USE_INLINE_METRICS = False
try:
    from app.core.metrics import router_metrics  # se você criou app/core/metrics.py
except Exception:
    router_metrics = None
    USE_INLINE_METRICS = True
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, REGISTRY

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    setup_logging()

    # instancia única do repositório e override de dependência (evita recriar cliente Dynamo a cada request)
    if VideoRepo is not None:
        app.state.video_repo = VideoRepo()
        try:
            # override do provider definido em app/routers/videos.py
            app.dependency_overrides[videos_router.get_video_repo] = lambda: app.state.video_repo
        except Exception:
            # se a função get_video_repo mudar de lugar, evitamos crash
            pass

    try:
        yield
    finally:
        # shutdown
        try:
            app.dependency_overrides.clear()
        except Exception:
            pass

# --- App ---
app = FastAPI(title="Video Service", version="0.1.0", lifespan=lifespan)

# CORS básico (ajuste para sua necessidade)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de observabilidade (se disponível)
if ObservabilityMiddleware:
    app.add_middleware(ObservabilityMiddleware)

# Routers
app.include_router(videos_router.router)
if health_router:
    app.include_router(health_router.router)

# /metrics (usa router se existir; senão cria inline)
if router_metrics:
    app.include_router(router_metrics)
elif USE_INLINE_METRICS:
    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

# Health simples (fallback caso você não tenha o router de health)
if not health_router:
    @app.get("/health")
    def health():
        return {"status": "ok"}
