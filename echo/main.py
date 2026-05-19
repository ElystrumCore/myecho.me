from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from echo.api.auth import router as auth_router
from echo.api.comments import router as comments_router
from echo.api.dashboard import router as dashboard_router
from echo.api.echo import router as echo_router
from echo.api.exchange import router as exchange_router
from echo.api.ingest import router as ingest_router
from echo.api.journal import router as journal_router
from echo.api.profile import router as profile_router
from echo.api.theme import router as theme_router
from echo.api.voice import router as voice_router
from echo.config import settings
from echo.database import SessionLocal

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Your voice, persisting.",
)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# React owner dashboard (BlockNote editor). Vite outputs to
# echo/static/dashboard/ (see frontend/vite.config.ts → build.outDir).
# Mounted with html=True so client-side routing works (SPA fallback to
# index.html for unknown sub-paths). Guarded by dist presence so dev runs
# without first running `pnpm build` in frontend/ stay fine.
dashboard_dist = static_dir / "dashboard"
if (dashboard_dist / "index.html").exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(dashboard_dist), html=True),
        name="dashboard",
    )

# API routes
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(ingest_router, prefix="/api/ingest", tags=["ingest"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
app.include_router(echo_router, prefix="/api/echo", tags=["echo"])
app.include_router(journal_router, prefix="/api/journal", tags=["journal"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(theme_router, prefix="/api/echo", tags=["theme"])
app.include_router(comments_router, prefix="/api/journal", tags=["comments"])
app.include_router(exchange_router, prefix="/exchange", tags=["exchange"])
# PGE integration: voice generation endpoint at /voice/generate matching
# myecho_client contract. See echo/api/voice.py for the contract.
app.include_router(voice_router, prefix="/voice", tags=["voice-pge"])


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
    """Public journal stream for a user.

    Cached for 5 min in Redis (key=echo:journal:{username}) to avoid the
    4-query PG fanout on every page hit. Invalidate via `cache.invalidate_journal`
    on entry publish / profile rebuild.
    """
    from echo import cache as echo_cache
    from echo.models.journal import EntryStatus, JournalContent, JournalEntry
    from echo.models.profile import EchoProfile
    from echo.models.user import User

    cached = echo_cache.journal_data(username)
    if cached is not None:
        return templates.TemplateResponse(request, "journal.html", cached)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return templates.TemplateResponse(
                request,
                "journal.html",
                {
                    "username": username,
                    "display_name": username,
                    "entries": [],
                    "stats": {},
                },
            )

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

        ctx = {
            "username": username,
            "display_name": user.display_name,
            "entries": entry_data,
            "stats": stats,
        }
        # Cache without the request object (Request is not JSON-serializable).
        echo_cache.set_journal_data(username, ctx)
        return templates.TemplateResponse(request, "journal.html", ctx)
    finally:
        db.close()


@app.get("/echo/{username}/ask", response_class=HTMLResponse)
async def ask_page(username: str, request: Request):
    """Public Ask page."""
    from echo.models.profile import EchoProfile
    from echo.models.user import User

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

        return templates.TemplateResponse(
            request,
            "ask.html",
            {
                "username": username,
                "display_name": display_name,
                "stats": stats,
            },
        )
    finally:
        db.close()


@app.post("/api/journal/{username}/ask")
async def public_ask(username: str, request: Request):
    """Public Ask endpoint — called by the ask.html form.

    Identical questions are cached for 1h (keyed by sha256(question)) to bound
    Claude API spend when a question goes viral or visitors retry the form.
    """
    from echo import cache as echo_cache
    from echo.engine.ask import respond
    from echo.models.profile import EchoProfile
    from echo.models.user import User

    body = await request.json()
    question = body.get("question", "")

    # Cache hit before any DB / Claude work.
    cached = echo_cache.ask_response(username, question)
    if cached is not None:
        return cached

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"response": "Echo not found.", "confidence": 0}

        profile = db.query(EchoProfile).filter(EchoProfile.user_id == user.id).first()
        if not profile or not profile.voice_prompt:
            return {"response": "Echo is still learning. Check back later.", "confidence": 0}

        result = respond(
            profile.voice_prompt,
            question,
            belief_graph=profile.belief_graph,
        )
        # Only cache successful responses with a real confidence signal so
        # transient errors don't poison the cache.
        if isinstance(result, dict) and result.get("confidence", 0) > 0:
            echo_cache.set_ask_response(username, question, result)
        return result
    finally:
        db.close()
