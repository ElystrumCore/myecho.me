import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from echo.api.auth import router as auth_router
from echo.api.comments import router as comments_router
from echo.api.dashboard import router as dashboard_router
from echo.api.echo import router as echo_router
from echo.api.ingest import router as ingest_router
from echo.api.journal import router as journal_router
from echo.api.profile import router as profile_router
from echo.api.theme import router as theme_router
from echo.config import settings
from echo.database import get_db, SessionLocal

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Your voice, persisting.",
)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# API routes
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(ingest_router, prefix="/api/ingest", tags=["ingest"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
app.include_router(echo_router, prefix="/api/echo", tags=["echo"])
app.include_router(journal_router, prefix="/api/journal", tags=["journal"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(theme_router, prefix="/api/echo", tags=["theme"])
app.include_router(comments_router, prefix="/api/journal", tags=["comments"])


@app.get("/")
async def root():
    return {"name": "Echo", "tagline": "Your voice, persisting.", "version": settings.app_version}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Public journal pages (Jinja2 server-rendered)
# ---------------------------------------------------------------------------

@app.get("/echo/{username}", response_class=HTMLResponse)
async def journal_page(username: str, request: Request):
    """Public journal stream for a user."""
    from echo.models.user import User
    from echo.models.journal import JournalEntry, JournalContent, EntryStatus
    from echo.models.profile import EchoProfile

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return templates.TemplateResponse("journal.html", {
                "request": request, "username": username,
                "display_name": username, "entries": [], "stats": {},
            })

        entries = (
            db.query(JournalEntry)
            .filter(JournalEntry.user_id == user.id, JournalEntry.status == EntryStatus.published)
            .order_by(JournalEntry.published_at.desc())
            .limit(20)
            .all()
        )

        entry_data = []
        for e in entries:
            content = db.query(JournalContent).filter(JournalContent.entry_id == e.id).first()
            entry_data.append({
                "id": str(e.id),
                "title": e.title,
                "content": content.body if content else "",
                "published_at": e.published_at,
                "topic_tags": [],
            })

        # Pull real stats from profile
        profile = db.query(EchoProfile).filter(EchoProfile.user_id == user.id).first()
        stats = {}
        if profile and profile.style_fingerprint:
            fp = profile.style_fingerprint
            stats["total_messages"] = f"{fp.get('structure', {}).get('total_messages', 0):,}"
            stats["sources"] = len(fp.get("sources", {}))

        return templates.TemplateResponse("journal.html", {
            "request": request,
            "username": username,
            "display_name": user.display_name,
            "entries": entry_data,
            "stats": stats,
        })
    finally:
        db.close()


@app.get("/echo/{username}/ask", response_class=HTMLResponse)
async def ask_page(username: str, request: Request):
    """Public Ask page."""
    from echo.models.user import User
    from echo.models.profile import EchoProfile

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        display_name = user.display_name if user else username

        stats = {}
        if user:
            profile = db.query(EchoProfile).filter(EchoProfile.user_id == user.id).first()
            if profile and profile.style_fingerprint:
                fp = profile.style_fingerprint
                stats["total_messages"] = f"{fp.get('structure', {}).get('total_messages', 0):,}"
                stats["sources"] = len(fp.get("sources", {}))

        return templates.TemplateResponse("ask.html", {
            "request": request,
            "username": username,
            "display_name": display_name,
            "stats": stats,
        })
    finally:
        db.close()


@app.post("/api/journal/{username}/ask")
async def public_ask(username: str, request: Request):
    """Public Ask endpoint — called by the ask.html form."""
    from echo.models.user import User
    from echo.models.profile import EchoProfile
    from echo.engine.ask import respond

    body = await request.json()
    question = body.get("question", "")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"response": "Echo not found.", "confidence": 0}

        profile = db.query(EchoProfile).filter(EchoProfile.user_id == user.id).first()
        if not profile or not profile.voice_prompt:
            return {"response": "Echo is still learning. Check back later.", "confidence": 0}

        result = respond(profile.voice_prompt, question)
        return result
    finally:
        db.close()
