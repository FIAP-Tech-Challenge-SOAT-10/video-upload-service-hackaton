from fastapi import FastAPI
from .routers import videos

app = FastAPI(title="Video Service", version="0.1.0")
app.include_router(videos.router)

@app.get("/health")
def health():
    return {"status": "ok"}
