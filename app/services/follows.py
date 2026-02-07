"""关注服务"""

import sqlite3
from typing import List
from app.services.auth import now_iso


def follow_user(conn: sqlite3.Connection, follower_id: int, followed_id: int) -> bool:
    """关注用户"""
    if follower_id == followed_id:
        raise ValueError("不能关注自己")
    
    try:
        conn.execute(
            "INSERT INTO follows(follower_id, followed_id, created_at) VALUES (?, ?, ?)",
            (follower_id, followed_id, now_iso())
        )
        return True
    except sqlite3.IntegrityError:
        return False


def unfollow_user(conn: sqlite3.Connection, follower_id: int, followed_id: int) -> bool:
    """取消关注"""
    result = conn.execute(
        "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
        (follower_id, followed_id)
    )
    return result.rowcount > 0


def is_following(conn: sqlite3.Connection, follower_id: int, followed_id: int) -> bool:
    """检查是否已关注"""
    result = conn.execute(
        "SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
        (follower_id, followed_id)
    ).fetchone()
    return bool(result)


def get_followers(conn: sqlite3.Connection, user_id: int, limit: int = 20) -> List[sqlite3.Row]:
    """获取粉丝列表"""
    return conn.execute(
        """
        SELECT u.id, u.username, u.display_name, u.bio, u.avatar_path
        FROM users u
        JOIN follows f ON f.follower_id = u.id
        WHERE f.followed_id = ?
        ORDER BY f.created_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    ).fetchall()


def get_following(conn: sqlite3.Connection, user_id: int, limit: int = 20) -> List[sqlite3.Row]:
    """获取关注列表"""
    return conn.execute(
        """
        SELECT u.id, u.username, u.display_name, u.bio, u.avatar_path
        FROM users u
        JOIN follows f ON f.followed_id = u.id
        WHERE f.follower_id = ?
        ORDER BY f.created_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    ).fetchall()


def get_follow_counts(conn: sqlite3.Connection, user_id: int) -> dict:
    """获取关注/粉丝数量"""
    followers = conn.execute(
        "SELECT COUNT(*) FROM follows WHERE followed_id = ?", (user_id,)
    ).fetchone()[0]
    
    following = conn.execute(
        "SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user_id,)
    ).fetchone()[0]
    
    return {"followers": followers, "following": following}
