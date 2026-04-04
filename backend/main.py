from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import metrics, healing
from db.database import init_db

app = FastAPI(title="AutoHeal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(metrics.router)
app.include_router(healing.router)

@app.get("/")
def health_check():
    return {"status": "AutoHeal Backend Running"}