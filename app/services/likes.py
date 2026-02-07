"""点赞管理服务"""

import sqlite3
from app.services.auth import now_iso


def toggle_like(conn: sqlite3.Connection, post_id: int, user_id: int) -> bool:
    """
    切换点赞状态

    Args:
        conn: 数据库连接
        post_id: 帖子ID
        user_id: 用户ID

    Returns:
        True 表示已点赞，False 表示已取消点赞
    """
    # 检查是否已点赞
    existing = conn.execute(
        "SELECT id FROM post_likes WHERE post_id = ? AND user_id = ?",
        (post_id, user_id),
    ).fetchone()

    if existing:
        # 取消点赞
        conn.execute("DELETE FROM post_likes WHERE id = ?", (existing["id"],))
        conn.execute("UPDATE posts SET likes = likes - 1 WHERE id = ?", (post_id,))
        return False
    else:
        # 点赞
        conn.execute(
            "INSERT INTO post_likes(post_id, user_id, created_at) VALUES (?, ?, ?)",
            (post_id, user_id, now_iso()),
        )
        conn.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
        return True


def is_liked_by_user(conn: sqlite3.Connection, post_id: int, user_id: int) -> bool:
    """检查用户是否已点赞某帖子"""
    row = conn.execute(
        "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
        (post_id, user_id),
    ).fetchone()
    return row is not None


def get_like_count(conn: sqlite3.Connection, post_id: int) -> int:
    """获取帖子的点赞数"""
    row = conn.execute("SELECT likes FROM posts WHERE id = ?", (post_id,)).fetchone()
    return row["likes"] if row else 0
