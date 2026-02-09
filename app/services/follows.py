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


def get_following_feed_posts(
    conn: sqlite3.Connection,
    user_id: int,
    limit: int = 18,
    offset: int = 0
) -> List[sqlite3.Row]:
    """
    获取关注用户的帖子动态

    返回所有关注用户的帖子，按创建时间倒序排列
    """
    return conn.execute(
        """
        SELECT p.id, p.user_id, p.title, p.description, p.media_type, p.filename,
               p.thumbnail_path, p.source, p.prompt, p.likes, p.created_at,
               COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username,
               COALESCE(u.avatar_path, '') AS author_avatar
        FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE p.user_id IN (SELECT followed_id FROM follows WHERE follower_id = ?)
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset)
    ).fetchall()


def count_following_feed_posts(conn: sqlite3.Connection, user_id: int) -> int:
    """计算关注动态的帖子总数"""
    row = conn.execute(
        """
        SELECT COUNT(*) as count
        FROM posts
        WHERE user_id IN (SELECT followed_id FROM follows WHERE follower_id = ?)
        """,
        (user_id,)
    ).fetchone()
    return row["count"] if row else 0


def get_recommended_users(
    conn: sqlite3.Connection,
    user_id: int,
    limit: int = 10
) -> List[sqlite3.Row]:
    """
    获取推荐关注的用户

    按发帖数和粉丝数排序，排除已关注和自己
    """
    return conn.execute(
        """
        SELECT u.id, u.username, u.display_name, u.bio, u.avatar_path,
               COUNT(DISTINCT p.id) AS post_count,
               (SELECT COUNT(*) FROM follows f2 WHERE f2.followed_id = u.id) AS follower_count
        FROM users u
        LEFT JOIN posts p ON p.user_id = u.id
        WHERE u.id != ?
          AND u.id NOT IN (SELECT followed_id FROM follows WHERE follower_id = ?)
        GROUP BY u.id
        ORDER BY post_count DESC, follower_count DESC
        LIMIT ?
        """,
        (user_id, user_id, limit)
    ).fetchall()


def get_followed_user_ids(conn: sqlite3.Connection, user_id: int) -> set:
    """
    获取用户关注的所有用户ID集合

    用于批量检查关注状态
    """
    rows = conn.execute(
        "SELECT followed_id FROM follows WHERE follower_id = ?",
        (user_id,)
    ).fetchall()
    return {row["followed_id"] for row in rows}
