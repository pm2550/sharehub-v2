"""点赞路由"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.dependencies import require_auth, get_db_conn
from app.services.likes import toggle_like, is_liked_by_user
import sqlite3

router = APIRouter(tags=["likes"])


@router.post("/post/{post_id}/like")
async def like_post(
    post_id: int,
    request: Request,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """
    点赞/取消点赞帖子（toggle）

    返回JSON格式，支持AJAX调用
    """
    try:
        is_liked = toggle_like(db, post_id, user["id"])

        # 获取最新点赞数
        post = db.execute(
            "SELECT likes FROM posts WHERE id = ?", (post_id,)
        ).fetchone()

        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")

        return JSONResponse({
            "success": True,
            "liked": is_liked,
            "likes_count": post["likes"],
            "message": "已点赞" if is_liked else "已取消点赞"
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)
