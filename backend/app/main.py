from fastapi import FastAPI

from backend.app.core.config import get_settings


app = FastAPI(title=get_settings().app_name)


@app.get("/api/health")
def health():
    return {"ok": True}

