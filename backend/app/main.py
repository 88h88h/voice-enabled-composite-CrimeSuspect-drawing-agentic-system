from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import agora, chat, sessions, signoff
from app.database import init_db
from app.services.image_store import SKETCH_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Composite Sketch Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon demo scope; would be locked down for a real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(agora.router)
app.include_router(signoff.router)

app.mount("/sketches", StaticFiles(directory=str(SKETCH_DIR)), name="sketches")


@app.get("/health")
async def health():
    return {"status": "ok"}
