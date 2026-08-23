import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import agora, chat, sessions, signoff
from app.database import init_db
from app.services.image_store import SKETCH_DIR

# Without this, Python's logging has no configured handler and silently
# drops everything below WARNING (INFO-level turn/reply logging in chat.py
# would never actually appear) -- this is what makes those visible.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

logger = logging.getLogger("app")


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


# Unhandled exceptions raised inside a route bypass CORSMiddleware's
# response processing (Starlette's default ServerErrorMiddleware sits
# outside it), so a cross-origin browser client sees a bare network error
# ("Failed to fetch") instead of the real status/body -- hiding exactly the
# information needed to debug it. Registered exception handlers run INSIDE
# the middleware stack, so their responses get CORS headers applied
# correctly. This is general robustness, not specific to any one endpoint.
@app.exception_handler(httpx.HTTPStatusError)
async def upstream_api_error_handler(request: Request, exc: httpx.HTTPStatusError):
    logger.error("upstream API error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": f"Upstream API error: {exc}"})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled error in %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})
