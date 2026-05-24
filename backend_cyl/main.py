from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.features.auth.router import router as auth_router
from app.features.sessions.router import router as sessions_router


app = FastAPI(title="swxy cyl minimal auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root() -> dict:
    return {
        "message": "backend_cyl is running",
        "docs": "/docs",
        "frontend": "http://127.0.0.1:5173",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(sessions_router)
