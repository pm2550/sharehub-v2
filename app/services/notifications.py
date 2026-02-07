"""通知服务"""

import sqlite3
from typing import List
from app.services.auth import now_iso


def create_notification(
    conn: sqlite3.Connection,
    user_id: int,
    type: str,
    message: str,
    source_user_id: int = None,
    post_id: int = None,
    comment_id: int = None
):
    """创建通知"""
    conn.execute(
        """
        INSERT INTO notifications(user_id, type, source_user_id, post_id, comment_id, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, type, source_user_id, post_id, comment_id, message, now_iso())
    )


def get_user_notifications(conn: sqlite3.Connection, user_id: int, limit: int = 20) -> List[sqlite3.Row]:
    """获取用户的通知列表"""
    return conn.execute(
        """
        SELECT n.*, COALESCE(u.display_name, u.username, 'someone') as source_user_name
        FROM notifications n
        LEFT JOIN users u ON u.id = n.source_user_id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    ).fetchall()


def mark_as_read(conn: sqlite3.Connection, notification_id: int, user_id: int):
    """标记通知为已读"""
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, user_id)
    )


def mark_all_as_read(conn: sqlite3.Connection, user_id: int):
    """标记所有通知为已读"""
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
        (user_id,)
    )


def get_unread_count(conn: sqlite3.Connection, user_id: int) -> int:
    """获取未读通知数量"""
    return conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
