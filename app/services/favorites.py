"""收藏/书签管理服务"""

import sqlite3
from typing import List
from app.services.auth import now_iso


def toggle_favorite(conn: sqlite3.Connection, post_id: int, user_id: int) -> bool:
    """
    切换收藏状态

    Args:
        conn: 数据库连接
        post_id: 帖子ID
        user_id: 用户ID

    Returns:
        True 表示已收藏，False 表示已取消收藏
    """
    # 检查是否已收藏
    existing = conn.execute(
        "SELECT id FROM favorites WHERE post_id = ? AND user_id = ?",
        (post_id, user_id),
    ).fetchone()

    if existing:
        # 取消收藏
        conn.execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
        return False
    else:
        # 收藏
        conn.execute(
            "INSERT INTO favorites(user_id, post_id, created_at) VALUES (?, ?, ?)",
            (user_id, post_id, now_iso()),
        )
        return True


def is_favorited_by_user(conn: sqlite3.Connection, post_id: int, user_id: int) -> bool:
    """检查用户是否已收藏某帖子"""
    row = conn.execute(
        "SELECT 1 FROM favorites WHERE post_id = ? AND user_id = ?",
        (post_id, user_id),
    ).fetchone()
    return row is not None


def get_favorite_count(conn: sqlite3.Connection, post_id: int) -> int:
    """获取帖子的收藏数"""
    row = conn.execute(
        "SELECT COUNT(*) as count FROM favorites WHERE post_id = ?",
        (post_id,)
    ).fetchone()
    return row["count"] if row else 0


def get_user_favorites(
    conn: sqlite3.Connection,
    user_id: int,
    limit: int = 18,
    offset: int = 0
) -> List[sqlite3.Row]:
    """
    获取用户的收藏列表

    返回带作者信息的帖子列表，按收藏时间倒序排列
    """
    return conn.execute(
        """
        SELECT p.id, p.user_id, p.title, p.description, p.media_type, p.filename,
               p.thumbnail_path, p.source, p.prompt, p.likes, p.created_at,
               COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username,
               COALESCE(u.avatar_path, '') AS author_avatar,
               f.created_at AS favorited_at
        FROM favorites f
        JOIN posts p ON p.id = f.post_id
        LEFT JOIN users u ON u.id = p.user_id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset)
    ).fetchall()


def count_user_favorites(conn: sqlite3.Connection, user_id: int) -> int:
    """计算用户的收藏总数"""
    row = conn.execute(
        "SELECT COUNT(*) as count FROM favorites WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    return row["count"] if row else 0


def get_favorited_post_ids(conn: sqlite3.Connection, user_id: int, post_ids: List[int]) -> set:
    """
    批量检查用户收藏状态

    Args:
        user_id: 用户ID
        post_ids: 帖子ID列表

    Returns:
        用户已收藏的帖子ID集合
    """
    if not post_ids:
        return set()

    placeholders = ",".join("?" * len(post_ids))
    rows = conn.execute(
        f"SELECT post_id FROM favorites WHERE user_id = ? AND post_id IN ({placeholders})",
        [user_id] + post_ids
    ).fetchall()
    return {row["post_id"] for row in rows}
