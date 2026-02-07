"""JSON API 路由
供前端 AJAX 调用和未来移动端/第三方集成
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from app.dependencies import get_current_user
from app.db.connection import get_db
from app.services import posts as posts_service
from app.services import search as search_service
from app.services import tags as tags_service
from app.services import notifications as notifications_service
from app.services import ai_queue as ai_service

router = APIRouter(prefix="/api/v1", tags=["api"])


@router.get("/gallery")
def api_gallery(
    page: int = Query(1, ge=1),
    sort: str = Query("latest", regex="^(latest|popular|comments)$"),
    media_type: Optional[str] = Query(None, regex="^(image|video)$"),
    source: Optional[str] = Query(None, regex="^(upload|ai)$"),
    tag: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = Query(18, ge=1, le=100)
):
    """Gallery API - 分页获取帖子列表"""
    with get_db() as conn:
        posts, total = posts_service.get_posts_paginated(
            conn,
            page=page,
            page_size=limit,
            sort=sort,
            media_type=media_type,
            source=source,
            tag=tag,
            user_id=user_id
        )
    
    total_pages = max(1, (total + limit - 1) // limit)
    
    return {
        "posts": [dict(p) for p in posts],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }
    }


@router.get("/post/{post_id}")
def api_post_detail(post_id: int):
    """获取帖子详情"""
    with get_db() as conn:
        post = posts_service.get_post_by_id(conn, post_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    
    return dict(post)


@router.post("/post/{post_id}/like")
def api_toggle_like(post_id: int, user: dict = Depends(get_current_user)):
    """点赞/取消点赞"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    with get_db() as conn:
        is_liked = posts_service.toggle_like(conn, post_id, user['id'])
        post = posts_service.get_post_by_id(conn, post_id)
    
    return {
        "is_liked": is_liked,
        "likes_count": post['likes'] if post else 0
    }


@router.get("/search")
def api_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50)
):
    """搜索 API"""
    with get_db() as conn:
        results = search_service.search_all(conn, query=q, limit=limit)
    
    return {
        "query": q,
        "posts": [dict(p) for p in results.get('posts', [])],
        "users": [dict(u) for u in results.get('users', [])]
    }


@router.get("/tags/popular")
def api_popular_tags(limit: int = Query(20, ge=1, le=100)):
    """获取热门标签"""
    with get_db() as conn:
        tags = tags_service.get_popular_tags(conn, limit=limit)
    
    return {
        "tags": [dict(t) for t in tags]
    }


@router.get("/tags/autocomplete")
def api_tag_autocomplete(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50)
):
    """标签自动补全"""
    with get_db() as conn:
        tags = tags_service.search_tags(conn, query=q, limit=limit)
    
    return {
        "tags": [dict(t) for t in tags]
    }


@router.get("/notifications/unread-count")
def api_unread_notifications_count(user: dict = Depends(get_current_user)):
    """获取未读通知数"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    with get_db() as conn:
        count = notifications_service.get_unread_count(conn, user['id'])
    
    return {
        "unread_count": count
    }


@router.post("/notifications/{notification_id}/read")
def api_mark_notification_read(notification_id: int, user: dict = Depends(get_current_user)):
    """标记通知已读"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    with get_db() as conn:
        success = notifications_service.mark_as_read(conn, notification_id, user['id'])
    
    if not success:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    return {"success": True}


@router.post("/notifications/mark-all-read")
def api_mark_all_read(user: dict = Depends(get_current_user)):
    """标记所有通知已读"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    with get_db() as conn:
        notifications_service.mark_all_as_read(conn, user['id'])
    
    return {"success": True}


@router.get("/ai/status/{job_id}")
def api_ai_status(job_id: int, user: dict = Depends(get_current_user)):
    """查询 AI 任务状态"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    with get_db() as conn:
        job = ai_service.get_job_by_id(conn, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查权限
    if job['user_id'] != user['id'] and not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="无权访问")
    
    return dict(job)


@router.post("/ai/cancel/{job_id}")
def api_cancel_ai_job(job_id: int, user: dict = Depends(get_current_user)):
    """取消 AI 任务"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    
    with get_db() as conn:
        job = ai_service.get_job_by_id(conn, job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 检查权限
        if job['user_id'] != user['id'] and not user.get('is_admin'):
            raise HTTPException(status_code=403, detail="无权操作")
        
        # 只能取消 pending 状态的任务
        if job['status'] != 'pending':
            raise HTTPException(status_code=400, detail="只能取消等待中的任务")
        
        success = ai_service.cancel_job(conn, job_id)
    
    return {"success": success}
