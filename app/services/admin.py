"""管理后台服务"""

from typing import Optional, Dict, List
import sqlite3
from datetime import datetime, timezone
from app.db.connection import get_db


def get_dashboard_stats(conn: sqlite3.Connection) -> Dict:
    """获取仪表盘统计数据"""
    stats = {}
    
    # 用户统计
    stats['total_users'] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    stats['admin_users'] = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
    
    # 帖子统计
    stats['total_posts'] = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    stats['total_images'] = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE media_type = 'image' AND source = 'upload'"
    ).fetchone()[0]
    stats['total_videos'] = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE media_type = 'video'"
    ).fetchone()[0]
    stats['ai_generated'] = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE source = 'ai'"
    ).fetchone()[0]
    
    # AI 任务统计
    stats['ai_pending'] = conn.execute(
        "SELECT COUNT(*) FROM ai_jobs WHERE status = 'pending'"
    ).fetchone()[0]
    stats['ai_running'] = conn.execute(
        "SELECT COUNT(*) FROM ai_jobs WHERE status = 'running'"
    ).fetchone()[0]
    stats['ai_completed'] = conn.execute(
        "SELECT COUNT(*) FROM ai_jobs WHERE status = 'done'"
    ).fetchone()[0]
    stats['ai_failed'] = conn.execute(
        "SELECT COUNT(*) FROM ai_jobs WHERE status = 'failed'"
    ).fetchone()[0]
    
    # 举报统计（如果表存在）
    try:
        stats['pending_reports'] = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE status = 'pending'"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        stats['pending_reports'] = 0
    
    # 互动统计
    stats['total_comments'] = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    stats['total_likes'] = conn.execute("SELECT COUNT(*) FROM post_likes").fetchone()[0]
    
    return stats


def search_users(conn: sqlite3.Connection, query: str = "", page: int = 1, page_size: int = 20) -> tuple:
    """搜索用户"""
    offset = (page - 1) * page_size
    
    if query:
        where = "WHERE username LIKE ? OR display_name LIKE ?"
        params = (f"%{query}%", f"%{query}%")
        count_params = params
    else:
        where = ""
        params = ()
        count_params = ()
    
    total = conn.execute(
        f"SELECT COUNT(*) FROM users {where}",
        count_params
    ).fetchone()[0]
    
    users = conn.execute(
        f"""
        SELECT id, username, display_name, bio, is_admin, created_at,
               (SELECT COUNT(*) FROM posts WHERE user_id = users.id) as post_count
        FROM users
        {where}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        params + (page_size, offset)
    ).fetchall()
    
    return users, total


def toggle_admin_status(conn: sqlite3.Connection, user_id: int) -> bool:
    """切换用户管理员状态"""
    user = conn.execute(
        "SELECT is_admin FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    
    if not user:
        return False
    
    new_status = 0 if user['is_admin'] else 1
    conn.execute(
        "UPDATE users SET is_admin = ? WHERE id = ?",
        (new_status, user_id)
    )
    conn.commit()
    return True


def delete_user(conn: sqlite3.Connection, user_id: int) -> bool:
    """删除用户及其所有内容"""
    # 删除用户的帖子（级联会删除评论和点赞）
    conn.execute("DELETE FROM posts WHERE user_id = ?", (user_id,))
    
    # 删除用户的评论
    conn.execute("DELETE FROM comments WHERE user_id = ?", (user_id,))
    
    # 删除用户的点赞
    conn.execute("DELETE FROM post_likes WHERE user_id = ?", (user_id,))
    
    # 删除用户的AI任务
    conn.execute("DELETE FROM ai_jobs WHERE user_id = ?", (user_id,))
    
    # 删除用户
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    
    conn.commit()
    return True


def get_reports(conn: sqlite3.Connection, status: str = "pending", page: int = 1, page_size: int = 20) -> tuple:
    """获取举报列表"""
    offset = (page - 1) * page_size
    
    try:
        # 检查表是否存在
        conn.execute("SELECT 1 FROM reports LIMIT 1")
        
        if status:
            where = "WHERE r.status = ?"
            params = (status,)
            count_params = params
        else:
            where = ""
            params = ()
            count_params = ()
        
        total = conn.execute(
            f"SELECT COUNT(*) FROM reports r {where}",
            count_params
        ).fetchone()[0]
        
        reports = conn.execute(
            f"""
            SELECT r.id, r.reporter_id, r.post_id, r.comment_id, r.reason, r.status, r.created_at,
                   ru.username as reporter_username,
                   ru.display_name as reporter_name
            FROM reports r
            LEFT JOIN users ru ON ru.id = r.reporter_id
            {where}
            ORDER BY r.id DESC
            LIMIT ? OFFSET ?
            """,
            params + (page_size, offset)
        ).fetchall()
        
        return reports, total
    except sqlite3.OperationalError:
        # 表不存在，返回空结果
        return [], 0


def handle_report(conn: sqlite3.Connection, report_id: int, action: str) -> bool:
    """处理举报"""
    try:
        report = conn.execute(
            "SELECT * FROM reports WHERE id = ?",
            (report_id,)
        ).fetchone()
        
        if not report:
            return False
        
        if action == "approve":
            # 删除被举报的内容
            if report['post_id']:
                conn.execute("DELETE FROM posts WHERE id = ?", (report['post_id'],))
            elif report['comment_id']:
                conn.execute("DELETE FROM comments WHERE id = ?", (report['comment_id'],))
            
            conn.execute(
                "UPDATE reports SET status = 'approved' WHERE id = ?",
                (report_id,)
            )
        elif action == "reject":
            conn.execute(
                "UPDATE reports SET status = 'rejected' WHERE id = ?",
                (report_id,)
            )
        
        conn.commit()
        return True
    except sqlite3.OperationalError:
        return False


def get_recent_activity(conn: sqlite3.Connection, limit: int = 20) -> List[Dict]:
    """获取最近活动"""
    activities = []
    
    # 最近的帖子
    recent_posts = conn.execute(
        """
        SELECT p.id, p.title, p.created_at, u.username, u.display_name, 'post' as type
        FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
        ORDER BY p.id DESC
        LIMIT ?
        """,
        (limit // 2,)
    ).fetchall()
    
    for post in recent_posts:
        activities.append({
            'type': 'post',
            'id': post['id'],
            'title': post['title'],
            'username': post['username'] or 'legacy',
            'display_name': post['display_name'] or post['username'] or 'legacy',
            'created_at': post['created_at']
        })
    
    # 最近的用户
    recent_users = conn.execute(
        """
        SELECT id, username, display_name, created_at, 'user' as type
        FROM users
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit // 2,)
    ).fetchall()
    
    for user in recent_users:
        activities.append({
            'type': 'user',
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'] or user['username'],
            'created_at': user['created_at']
        })
    
    # 按时间排序
    activities.sort(key=lambda x: x['created_at'], reverse=True)
    
    return activities[:limit]
