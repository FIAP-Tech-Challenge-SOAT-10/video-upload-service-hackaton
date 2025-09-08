from fastapi import APIRouter

router = APIRouter(prefix="", tags=["health"])

@router.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
