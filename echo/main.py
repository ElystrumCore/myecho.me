from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from echo.config import settings
from echo.api.ingest import router as ingest_router
from echo.api.profile import router as profile_router
from echo.api.echo import router as echo_router
from echo.api.journal import router as journal_router
from echo.api.dashboard import router as dashboard_router
from echo.api.theme import router as theme_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Your voice, persisting.",
)

app.mount("/static", StaticFiles(directory="echo/static"), name="static")
templates = Jinja2Templates(directory="echo/templates")

# API routes
app.include_router(ingest_router, prefix="/api/ingest", tags=["ingest"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
app.include_router(echo_router, prefix="/api/echo", tags=["echo"])
app.include_router(journal_router, prefix="/api/journal", tags=["journal"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(theme_router, prefix="/api/echo", tags=["theme"])


@app.get("/")
async def root():
    return {"name": "Echo", "tagline": "Your voice, persisting.", "version": settings.app_version}


@app.get("/health")
async def health():
    return {"status": "ok"}
