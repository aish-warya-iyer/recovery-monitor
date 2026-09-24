"""Recovery Monitor local control plane (FastAPI). Run from recovery-monitor-backend/:

    uvicorn main:app --host 127.0.0.1 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import AI_ENDPOINTS, CORS_ORIGINS
from app.guards import assert_local
from app.routes import legacy_api, patients, review, sessions, system


@asynccontextmanager
async def lifespan(_app: FastAPI):
    assert_local(AI_ENDPOINTS)  # refuse to run if any AI endpoint is off the device (#21)
    db.conn()
    db.all_("SELECT 1")
    # Sessions interrupted by a restart would otherwise look "processing" forever.
    with db.tx() as c:
        c.execute("UPDATE sessions SET status = 'failed', stage = 'failed', error = 'Interrupted by a server restart; "
                  "please upload again.' WHERE status IN ('uploaded', 'processing')")
    yield


app = FastAPI(title="Recovery Monitor Local Control Plane", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])

# Order matters: legacy /api/sessions/{id}/check-in and /decision are more specific than nothing
# in the new routers, and the new routers never define those exact paths.
for r in (system.router, patients.router, sessions.router, review.router, legacy_api.router):
    app.include_router(r)
