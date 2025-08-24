from fastapi import APIRouter

router = APIRouter()

@router.get("/report/health")
async def health_check():
    return {"status": "ok"}