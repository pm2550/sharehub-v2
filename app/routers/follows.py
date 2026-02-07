"""关注路由"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from app.config import get_settings
from app.dependencies import get_db_conn, get_current_user, require_auth
from app.services.follows import follow_user, unfollow_user, is_following, get_followers, get_following
from app.services.users import get_user_by_username
from app.services.notifications import create_notification

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.APP_DIR / "templates"))

router = APIRouter(tags=["follows"])


def render(request: Request, template: str, context: dict, db = None):
    base = {
        "request": request,
        "site_title": settings.SITE_TITLE,
        "current_user": get_current_user(request, db) if db else None,
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


@router.post("/user/{username}/follow")
def toggle_follow(
    request: Request,
    username: str,
    db: sqlite3.Connection = Depends(get_db_conn),
    current_user: dict = Depends(require_auth)
):
    """关注/取消关注用户"""
    target_user = get_user_by_username(db, username)
    if not target_user:
        return JSONResponse(
            status_code=404,
            content={"error": "用户不存在"}
        )

    follower_id = current_user["id"]
    followed_id = target_user["id"]

    if follower_id == followed_id:
        return JSONResponse(
            status_code=400,
            content={"error": "不能关注自己"}
        )

    try:
        # 检查是否已关注
        if is_following(db, follower_id, followed_id):
            # 取消关注
            unfollow_user(db, follower_id, followed_id)
            action = "unfollowed"
        else:
            # 关注
            follow_user(db, follower_id, followed_id)
            action = "followed"

            # 创建通知
            create_notification(
                db,
                user_id=followed_id,
                type="follow",
                message=f"{current_user['username']} 关注了你",
                source_user_id=follower_id
            )

        db.commit()

        # 获取更新后的关注/粉丝数
        followers_count = len(get_followers(db, followed_id))
        following_count = len(get_following(db, followed_id))

        return JSONResponse(content={
            "success": True,
            "action": action,
            "followers_count": followers_count,
            "following_count": following_count
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/user/{username}/followers")
def followers_page(
    request: Request,
    username: str,
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """粉丝列表页面"""
    user = get_user_by_username(db, username)
    if not user:
        return render(request, "error.html", {
            "error": "用户不存在",
            "message": f"未找到用户: {username}"
        }, db)

    followers = get_followers(db, user["id"])

    return render(
        request,
        "followers.html",
        {
            "active": "",
            "profile_user": user,
            "followers": followers,
        },
        db,
    )


@router.get("/user/{username}/following")
def following_page(
    request: Request,
    username: str,
    db: sqlite3.Connection = Depends(get_db_conn)
):
    """关注列表页面"""
    user = get_user_by_username(db, username)
    if not user:
        return render(request, "error.html", {
            "error": "用户不存在",
            "message": f"未找到用户: {username}"
        }, db)

    following = get_following(db, user["id"])

    return render(
        request,
        "following.html",
        {
            "active": "",
            "profile_user": user,
            "following": following,
        },
        db,
    )
