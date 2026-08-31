from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.models.db import init_db
from app.api.routes import router
from app.api.rescue_routes import router as rescue_router
from app.rescue.job_store import init_rescue_db

app = FastAPI(
    title="PrivaLens DataRescue",
    description="Privacy red-team API: attack, detect, explain, fix and re-test "
                "anonymized datasets for re-identification risk. Also includes the "
                "DataRescue autonomous rescue-job API (/api/rescue/*).",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    init_rescue_db()


@app.get("/")
def root():
    return {"status": "ok", "service": "PrivaLens DataRescue API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}


app.include_router(router)
app.include_router(rescue_router)
