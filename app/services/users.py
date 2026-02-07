"""用户服务"""

import sqlite3
from typing import Optional

def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[sqlite3.Row]:
    """根据用户名获取用户"""
    return conn.execute(
        """
        SELECT id, username, display_name, bio, avatar_path, theme_preference, created_at
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    """根据用户 ID 获取用户"""
    return conn.execute(
        """
        SELECT id, username, display_name, bio, avatar_path, theme_preference, created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()


def update_user_profile(conn: sqlite3.Connection, user_id: int, display_name: str = None, bio: str = None) -> bool:
    """更新用户资料"""
    if display_name is not None:
        conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (display_name, user_id)
        )
    if bio is not None:
        conn.execute(
            "UPDATE users SET bio = ? WHERE id = ?",
            (bio, user_id)
        )
    return True


def update_user_avatar(conn: sqlite3.Connection, user_id: int, avatar_path: str) -> bool:
    """更新用户头像"""
    conn.execute(
        "UPDATE users SET avatar_path = ? WHERE id = ?",
        (avatar_path, user_id)
    )
    return True
