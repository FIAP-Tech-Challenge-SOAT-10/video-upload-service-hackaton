# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import videos as videos_router
from app.infrastructure.repositories.video_repo import VideoRepo

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.video_repo = VideoRepo()
    app.dependency_overrides[videos_router.get_video_repo] = lambda: app.state.video_repo
    try:
        yield
    finally:
        # shutdown (opcional)
        app.dependency_overrides.clear()

app = FastAPI(title="Video Service", version="0.1.0", lifespan=lifespan)

# routers
app.include_router(videos_router.router)

@app.get("/health")
def health():
    return {"status": "ok"}
