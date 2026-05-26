from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.router.chat_rt import router as chat_router
from app.router.history_rt import router as history_router
from app.router.user_rt import router as user_router


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


app.include_router(chat_router)
app.include_router(user_router)
app.include_router(history_router)
