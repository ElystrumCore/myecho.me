"""Comment API — threaded comments on journal entries.

Visitors don't need accounts. They provide a display name and get a
session-based visitor_id. Comments are threaded using the LJ talk2
pattern (parent_id for nesting, node_type for content type).

Owner can moderate: hide or delete comments.
"""

import uuid
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.journal import (
    Comment,
    CommentStatus,
    EntrySecurity,
    EntryStatus,
    JournalEntry,
)
from echo.models.user import User

router = APIRouter()


class CommentCreate(BaseModel):
    author_name: str
    body: str
    parent_id: str | None = None


class CommentModerate(BaseModel):
    action: str  # "hide" or "delete"


def _visitor_id(request: Request) -> str:
    """Generate a stable visitor ID from request headers.

    No account required — hash the IP + User-Agent for a session-stable identifier.
    Not meant to be bulletproof identity, just consistent within a session.
    """
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    return sha256(f"{ip}:{ua}".encode()).hexdigest()[:24]


def _get_entry_or_404(username: str, entry_id: str, db: Session) -> JournalEntry:
    """Get a published, public entry or raise 404."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    entry = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == user.id,
            JournalEntry.status == EntryStatus.published,
            JournalEntry.security == EntrySecurity.public,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


# --- Public endpoints (visitors) ---


@router.get("/{username}/entry/{entry_id}/comments")
async def list_comments(
    username: str,
    entry_id: str,
    db: Session = Depends(get_db),
):
    """Get all active comments on an entry, threaded."""
    entry = _get_entry_or_404(username, entry_id, db)
    comments = (
        db.query(Comment)
        .filter(
            Comment.entry_id == entry.id,
            Comment.status == CommentStatus.active,
        )
        .order_by(Comment.created_at.asc())
        .all()
    )

    # Build threaded structure: top-level comments + nested replies
    comment_map: dict[str, dict] = {}
    top_level: list[dict] = []

    for c in comments:
        node = {
            "id": str(c.id),
            "author_name": c.author_name,
            "body": c.body,
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "created_at": c.created_at.isoformat(),
            "replies": [],
        }
        comment_map[str(c.id)] = node

    for node in comment_map.values():
        if node["parent_id"] and node["parent_id"] in comment_map:
            comment_map[node["parent_id"]]["replies"].append(node)
        else:
            top_level.append(node)

    return {"entry_id": entry_id, "comments": top_level}


@router.post("/{username}/entry/{entry_id}/comments")
async def create_comment(
    username: str,
    entry_id: str,
    comment: CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Post a comment on a journal entry. No account required."""
    entry = _get_entry_or_404(username, entry_id, db)

    if not comment.body.strip():
        raise HTTPException(status_code=400, detail="Comment body cannot be empty")
    if not comment.author_name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    # Validate parent exists if replying
    if comment.parent_id:
        parent = (
            db.query(Comment)
            .filter(
                Comment.id == comment.parent_id,
                Comment.entry_id == entry.id,
                Comment.status == CommentStatus.active,
            )
            .first()
        )
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")

    new_comment = Comment(
        entry_id=entry.id,
        parent_id=uuid.UUID(comment.parent_id) if comment.parent_id else None,
        visitor_id=_visitor_id(request),
        author_name=comment.author_name.strip(),
        body=comment.body.strip(),
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return {
        "id": str(new_comment.id),
        "author_name": new_comment.author_name,
        "body": new_comment.body,
        "parent_id": str(new_comment.parent_id) if new_comment.parent_id else None,
        "created_at": new_comment.created_at.isoformat(),
    }


# --- Owner moderation endpoints ---


@router.put("/{user_id}/comments/{comment_id}/moderate")
async def moderate_comment(
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
    moderation: CommentModerate,
    db: Session = Depends(get_db),
):
    """Owner moderates a comment: hide or delete."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Verify the entry belongs to this user
    entry = db.query(JournalEntry).filter(JournalEntry.id == comment.entry_id).first()
    if not entry or entry.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your entry")

    if moderation.action == "hide":
        comment.status = CommentStatus.hidden
    elif moderation.action == "delete":
        comment.status = CommentStatus.deleted
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {moderation.action}")

    db.commit()
    return {"comment_id": str(comment.id), "status": comment.status}
