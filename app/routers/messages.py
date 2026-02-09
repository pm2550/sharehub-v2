"""私信路由"""

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from typing import Optional

from app.config import get_settings
from app.dependencies import require_auth, get_db_conn, get_current_user
from app.services.users import get_user_by_username
from app.services.messages import (
    send_message, get_conversations, get_conversation_messages,
    mark_conversation_read, get_total_unread_count, get_new_messages
)
from app.services.notifications import create_notification

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["messages"])


def render(request: Request, template: str, context: dict, db: sqlite3.Connection):
    """渲染模板的辅助函数"""
    user = get_current_user(request, db)
    unread_count = 0
    if user:
        unread_count = get_total_unread_count(db, user["id"])

    context.update({
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": user,
        "unread_message_count": unread_count,
    })
    return templates.TemplateResponse(template, context)


@router.get("/messages")
def messages_list(
    request: Request,
    page: int = Query(1, ge=1),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """对话列表页面"""
    limit = 20
    offset = (page - 1) * limit
    conversations = get_conversations(db, user["id"], limit, offset)

    return render(
        request,
        "messages.html",
        {
            "active": "messages",
            "page_title": "我的私信",
            "conversations": conversations,
            "page": page,
        },
        db,
    )


@router.get("/messages/{username}")
def conversation_detail(
    username: str,
    request: Request,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """对话详情页面"""
    partner = get_user_by_username(db, username)
    if not partner:
        raise HTTPException(status_code=404, detail="用户不存在")

    if partner["id"] == user["id"]:
        return JSONResponse({"error": "不能给自己发消息"}, status_code=400)

    # 标记已读
    mark_conversation_read(db, user["id"], partner["id"])
    db.commit()

    # 获取消息（包含帖子预览信息）
    messages = get_conversation_messages(db, user["id"], partner["id"], limit=50)

    return render(
        request,
        "conversation.html",
        {
            "active": "messages",
            "page_title": f"与 {partner['display_name'] or partner['username']} 的对话",
            "partner": partner,
            "messages": messages,
        },
        db,
    )


@router.post("/messages/{username}/send")
async def send_msg(
    username: str,
    request: Request,
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """AJAX 发送消息（支持附带帖子卡片）"""
    try:
        data = await request.json()
        content = data.get("content", "").strip()
        post_id = data.get("post_id")

        # 转换 post_id
        if post_id is not None:
            try:
                post_id = int(post_id)
            except (ValueError, TypeError):
                post_id = None

        if not content and not post_id:
            return JSONResponse({"success": False, "error": "内容不能为空"}, status_code=400)

        partner = get_user_by_username(db, username)
        if not partner:
            return JSONResponse({"success": False, "error": "用户不存在"}, status_code=404)

        # 发送
        msg_id = send_message(db, user["id"], partner["id"], content, post_id=post_id)

        # 创建通知
        create_notification(
            db,
            user_id=partner["id"],
            type="message",
            message=f"收到来自 {user['display_name'] or user['username']} 的私信",
            source_user_id=user["id"],
        )

        db.commit()

        # 构建响应（包含帖子预览给前端立即渲染）
        response_data = {
            "success": True,
            "message_id": msg_id,
            "content": content or "[分享帖子]",
            "post_id": post_id,
            "post": None,
            "created_at": "刚刚",
        }

        if post_id:
            post = db.execute(
                """
                SELECT p.id, p.title, p.media_type, p.filename, p.thumbnail_path,
                       p.likes, p.source,
                       COALESCE(u.display_name, u.username, 'legacy') AS author
                FROM posts p
                LEFT JOIN users u ON u.id = p.user_id
                WHERE p.id = ?
                """,
                (post_id,)
            ).fetchone()
            if post:
                response_data["post"] = dict(post)

        return JSONResponse(response_data)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/api/messages/unread-count")
def api_unread_count(
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """获取总未读数 API"""
    count = get_total_unread_count(db, user["id"])
    return {"count": count}


@router.get("/api/messages/{username}/poll")
def api_poll_messages(
    username: str,
    after_id: int = Query(0),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """轮询新消息 API（包含帖子预览）"""
    partner = get_user_by_username(db, username)
    if not partner:
        raise HTTPException(status_code=404, detail="User not found")

    new_messages = get_new_messages(db, user["id"], partner["id"], after_id=after_id)

    if new_messages:
        has_incoming = any(m["sender_id"] == partner["id"] for m in new_messages)
        if has_incoming:
            mark_conversation_read(db, user["id"], partner["id"])
            db.commit()

    res = []
    for m in new_messages:
        res.append({
            "id": m["id"],
            "sender_id": m["sender_id"],
            "content": m["content"],
            "post_id": m.get("post_id"),
            "post": m.get("post"),
            "created_at": m["created_at"],
            "is_me": m["sender_id"] == user["id"],
            "sender_avatar": m.get("sender_avatar", ""),
        })

    return {"messages": res}


@router.get("/api/messages/share-posts")
def api_share_posts(
    q: str = Query("", max_length=100),
    user: dict = Depends(require_auth),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """
    搜索可分享的帖子（用于聊天分享选择器）

    返回用户自己的帖子 + 收藏的帖子，支持关键词搜索
    """
    search_param = f"%{q}%" if q else "%"

    # 自己的帖子
    own_posts = db.execute(
        """
        SELECT p.id, p.title, p.media_type, p.filename, p.thumbnail_path,
               p.source, 'own' AS share_source
        FROM posts p
        WHERE p.user_id = ? AND p.title LIKE ?
        ORDER BY p.created_at DESC
        LIMIT 10
        """,
        (user["id"], search_param)
    ).fetchall()

    # 收藏的帖子
    fav_posts = db.execute(
        """
        SELECT p.id, p.title, p.media_type, p.filename, p.thumbnail_path,
               p.source, 'favorite' AS share_source
        FROM favorites f
        JOIN posts p ON p.id = f.post_id
        WHERE f.user_id = ? AND p.title LIKE ?
        ORDER BY f.created_at DESC
        LIMIT 10
        """,
        (user["id"], search_param)
    ).fetchall()

    # 合并去重
    seen = set()
    results = []
    for row in list(own_posts) + list(fav_posts):
        r = dict(row)
        if r["id"] not in seen:
            seen.add(r["id"])
            if r.get("thumbnail_path"):
                r["thumb_url"] = f"/media/{r['thumbnail_path']}"
            else:
                r["thumb_url"] = f"/media/{r['filename']}"
            results.append(r)

    return {"posts": results[:15]}
