"""
/voice/generate — voice-generation endpoint for PGE integration.

Wraps Echo's existing voice engine (echo/engine/voice.py) and exposes a
contract compatible with PGE's myecho_client. Maps PGE's
{register, audience, atom_payload} → an instruction string that flows
through the user's compiled voice_prompt.

For v1 (single-tenant CJ-only), the user is hardcoded to CJ's profile.
Multi-tenant Echo (per project_echo_roadmap) will replace the lookup
with per-request user identity once that work lands.
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from echo.api.auth_dep import get_authenticated_user
from echo.database import get_db
from echo.engine.voice import generate_text
from echo.models.profile import EchoProfile

router = APIRouter()


# v1 single-tenant: CJ's UUID from the seeded `cj` user.
# Overridable via env so the value isn't hardcoded forever.
DEFAULT_USER_ID = os.environ.get(
    "ECHO_DEFAULT_USER_ID", "4ec475a3-8db2-44ad-b2c8-2774890db8e6"
)


class VoiceGenerateRequest(BaseModel):
    register: str = Field(..., description="signal | field | technical | light")
    audience: str = Field("general", description="general | investor | cto | crew | community")
    atom_payload: dict = Field(..., description="atom payload (text/seed/topic/news_link)")
    max_tokens: int = Field(800, description="Max output tokens")
    temperature: float = Field(0.7, description="Sampling temperature (currently unused)")


class VoiceGenerateResponse(BaseModel):
    text: str
    register: str
    model_version: str | None = None


# Register × audience → instruction template. The voice_prompt itself
# already encodes "speak as CJ"; these templates inject the *frame* for
# the rewrite (POJ field crew vs. AetherCore investor vs. ElystrumCore CTO).
_REGISTER_TEMPLATES: dict[str, str | dict[str, str]] = {
    "signal": (
        "Rewrite the following as a LinkedIn post for your personal profile. "
        "Direct, story-led, observational. Lead with a hook in the first sentence. "
        "Stay in your voice — terse, specific, no corporate softening.\n\n"
        "Source: {text}"
    ),
    "field": (
        "Rewrite the following as a LinkedIn post for Peace Oil Jobs — your "
        "Peace Region oilfield community. Crew-aware, boots-on-ground framing. "
        "Reference real jobs/sites/conditions where it fits. Speak to the people "
        "swinging wrenches and the foremen running them. Stay in your voice.\n\n"
        "Source: {text}"
    ),
    "technical": {
        "investor": (
            "Rewrite the following as a LinkedIn post for the AetherCore Energy "
            "page — your gas-to-compute energy/AI infrastructure venture. Lead "
            "with the thesis. Make the financial/strategic angle explicit. "
            "Audience is energy + infra investors. Stay in your voice.\n\n"
            "Source: {text}"
        ),
        "cto": (
            "Rewrite the following as a LinkedIn post for the ElystrumCore.ai "
            "page — your AI orchestration platform. Frame as systems thinking, "
            "real-world AI adoption pitfalls, decision-maker level. Audience is "
            "CTOs and engineering leaders. Stay in your voice.\n\n"
            "Source: {text}"
        ),
        "general": (
            "Rewrite the following as a LinkedIn post on technical adoption / "
            "systems-thinking framing. Stay in your voice.\n\n"
            "Source: {text}"
        ),
    },
    "light": (
        "Rewrite the following as a LinkedIn post for a local Grande Prairie "
        "community audience — retail/community tone. Stay in your voice.\n\n"
        "Source: {text}"
    ),
}


def _build_instruction(register: str, audience: str, atom_text: str) -> str:
    template_entry = _REGISTER_TEMPLATES.get(register)
    if template_entry is None:
        # Unknown register — fall back to signal (CJ Personal voice).
        template_entry = _REGISTER_TEMPLATES["signal"]
    if isinstance(template_entry, dict):
        # Audience-keyed registers (e.g. technical/investor vs technical/cto).
        template = template_entry.get(audience) or template_entry.get("general") or next(iter(template_entry.values()))
    else:
        template = template_entry
    return template.format(text=atom_text)


@router.post("/generate", response_model=VoiceGenerateResponse)
def voice_generate(
    req: VoiceGenerateRequest,
    claims: dict = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> VoiceGenerateResponse:
    """Generate text in CJ's voice for a given register/audience.

    Looks up the default Echo profile (single-tenant v1), builds a
    register-specific instruction, and runs it through the voice engine.
    """
    try:
        user_uuid = uuid.UUID(DEFAULT_USER_ID)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid ECHO_DEFAULT_USER_ID: {DEFAULT_USER_ID}",
        ) from exc

    profile = (
        db.query(EchoProfile).filter(EchoProfile.user_id == user_uuid).first()
    )
    if profile is None or not profile.voice_prompt:
        raise HTTPException(
            status_code=503,
            detail=(
                "Echo profile not found or voice_prompt empty. Run ingest first."
            ),
        )

    atom_text = (req.atom_payload or {}).get("text", "")
    if not atom_text:
        raise HTTPException(
            status_code=400,
            detail="atom_payload.text is required and must be non-empty",
        )

    instruction = _build_instruction(req.register, req.audience, atom_text)

    try:
        text = generate_text(
            profile.voice_prompt, instruction, max_tokens=req.max_tokens
        )
    except RuntimeError as exc:
        # generate_text raises RuntimeError if anthropic SDK is missing.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return VoiceGenerateResponse(
        text=text,
        register=req.register,
        model_version="echo-1.13M",
    )


@router.post("/feedback", status_code=204)
def voice_feedback(
    payload: dict,
    claims: dict = Depends(get_authenticated_user),
) -> None:
    """Record an edit pair for future training-signal use.

    For v1 this is a best-effort no-op so the myecho_client.record_edit()
    call from PGE's edit handler doesn't fail. Future work: persist diffs
    to inform register prompt tuning.
    """
    # Payload shape (from myecho_client.record_edit):
    #   {"canonical": str, "edited": str, "register": str}
    # Intentionally silent for v1 — accept and discard.
    _ = payload
    return None
