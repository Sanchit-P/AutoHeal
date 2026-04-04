import os
from fastapi import APIRouter

router = APIRouter()

_ENABLE_CRASH = os.environ.get("ADMIN_ENABLE_CRASH", "0") == "1"

@router.post("/admin/crash")
def crash():
    if not _ENABLE_CRASH:
        return {"error": "disabled"}
    os._exit(1)  # type: ignore

