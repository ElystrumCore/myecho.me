import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.theme import ThemeConfig, ThemeGeneratedBy
from echo.models.profile import EchoProfile
from echo.engine.themes import generate_theme, get_base_theme, theme_to_css_vars

router = APIRouter()


class ThemeGenerateRequest(BaseModel):
    description: str
    base_template: str | None = None


class ThemeUpdateRequest(BaseModel):
    config: dict
    name: str | None = None


class CssOverrideRequest(BaseModel):
    css: str


@router.post("/{user_id}/theme/generate")
async def generate_user_theme(
    user_id: uuid.UUID,
    request: ThemeGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a theme from a natural language description.

    Optionally informed by the user's StyleFingerprint — a terse communicator
    gets a cleaner layout, a warm writer gets a more ornate design.
    """
    # Get fingerprint if available
    fingerprint = None
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if profile:
        fingerprint = profile.style_fingerprint

    config = generate_theme(request.description, style_fingerprint=fingerprint)

    # Save or update
    theme = db.query(ThemeConfig).filter(ThemeConfig.user_id == user_id).first()
    if theme:
        theme.config = config
        theme.description = request.description
        theme.generated_by = ThemeGeneratedBy.ai
        theme.base_template = request.base_template
        theme.version += 1
    else:
        theme = ThemeConfig(
            user_id=user_id,
            name=f"AI: {request.description[:60]}",
            description=request.description,
            config=config,
            generated_by=ThemeGeneratedBy.ai,
            base_template=request.base_template,
        )
        db.add(theme)

    db.commit()
    db.refresh(theme)

    return {
        "theme_id": theme.id,
        "config": theme.config,
        "css_vars": theme_to_css_vars(theme.config),
        "version": theme.version,
    }


@router.get("/{user_id}/theme")
async def get_theme(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get the current theme config for a user."""
    theme = db.query(ThemeConfig).filter(ThemeConfig.user_id == user_id).first()
    if not theme:
        # Return default dark theme
        default = get_base_theme("dark")
        return {
            "config": default,
            "css_vars": theme_to_css_vars(default),
            "name": "Default Dark",
            "generated_by": "template",
            "version": 0,
        }
    return {
        "config": theme.config,
        "css_vars": theme_to_css_vars(theme.config),
        "css_overrides": theme.css_overrides,
        "name": theme.name,
        "generated_by": theme.generated_by,
        "version": theme.version,
    }


@router.put("/{user_id}/theme")
async def update_theme(
    user_id: uuid.UUID,
    request: ThemeUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update theme config directly — for power users editing JSON."""
    theme = db.query(ThemeConfig).filter(ThemeConfig.user_id == user_id).first()
    if theme:
        theme.config = request.config
        if request.name:
            theme.name = request.name
        theme.generated_by = ThemeGeneratedBy.user
        theme.version += 1
    else:
        theme = ThemeConfig(
            user_id=user_id,
            name=request.name or "Custom",
            config=request.config,
            generated_by=ThemeGeneratedBy.user,
        )
        db.add(theme)

    db.commit()
    db.refresh(theme)
    return {"config": theme.config, "version": theme.version}


@router.put("/{user_id}/theme/css")
async def set_css_overrides(
    user_id: uuid.UUID,
    request: CssOverrideRequest,
    db: Session = Depends(get_db),
):
    """Set raw CSS overrides — the escape hatch for users who code."""
    theme = db.query(ThemeConfig).filter(ThemeConfig.user_id == user_id).first()
    if not theme:
        # Create with default + overrides
        theme = ThemeConfig(
            user_id=user_id,
            name="Custom CSS",
            config=get_base_theme("dark"),
            css_overrides=request.css,
            generated_by=ThemeGeneratedBy.user,
        )
        db.add(theme)
    else:
        theme.css_overrides = request.css
        theme.version += 1

    db.commit()
    return {"css_overrides": theme.css_overrides, "version": theme.version}


@router.post("/{user_id}/theme/preview")
async def preview_theme(
    user_id: uuid.UUID,
    request: ThemeGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a theme preview without saving — for iteration."""
    fingerprint = None
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if profile:
        fingerprint = profile.style_fingerprint

    config = generate_theme(request.description, style_fingerprint=fingerprint)

    return {
        "config": config,
        "css_vars": theme_to_css_vars(config),
        "preview": True,
    }
