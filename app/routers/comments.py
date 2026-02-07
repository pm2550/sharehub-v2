"""评论路由"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
import sqlite3

from app.dependencies import require_auth, get_db_conn
from app.services.auth import now_iso

router = APIRouter(tags=["comments"])


@router.post("/post/{post_id}/comment")
def comment(
    request: Request,
    post_id: int,
    content: str = Form(...),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """添加评论"""
    text = content.strip()
    if not text:
        return RedirectResponse(url=f"/post/{post_id}", status_code=303)

    db.execute(
        "INSERT INTO comments(post_id, user_id, author, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (post_id, user["id"], user["display_name"], text[:1000], now_iso()),
    )

    return RedirectResponse(url=f"/post/{post_id}", status_code=303)
