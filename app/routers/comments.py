"""评论路由"""

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
import sqlite3

from app.dependencies import require_auth, get_db_conn
from app.services.auth import now_iso

router = APIRouter(tags=["comments"])


def safe_next(target: str, default: str) -> str:
    if not target or not target.startswith("/") or target.startswith("//"):
        return default
    return target


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


@router.post("/comment/{comment_id}/delete")
def delete_comment(
    request: Request,
    comment_id: int,
    next: str = Form(""),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """删除评论 — 评论作者本人（个人页面）或管理员（帖子页面）"""
    comment = db.execute(
        "SELECT id, post_id, user_id FROM comments WHERE id = ?", (comment_id,)
    ).fetchone()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    is_author = bool(comment["user_id"] and comment["user_id"] == user["id"])
    if not is_author and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))

    return RedirectResponse(
        url=safe_next(next, f"/post/{comment['post_id']}"), status_code=303
    )
