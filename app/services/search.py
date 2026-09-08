"""搜索服务 - FTS5 全文搜索"""

import sqlite3
from typing import List, Tuple

def search_posts(conn: sqlite3.Connection, query: str, limit: int = 20) -> List[sqlite3.Row]:
    """
    搜索帖子（标题和描述）

    Args:
        conn: 数据库连接
        query: 搜索关键词
        limit: 返回数量限制

    Returns:
        匹配的帖子列表
    """
    if not query or not query.strip():
        return []

    # 使用 FTS5 MATCH 查询
    results = conn.execute(
        """
        SELECT p.id, p.title, p.description, p.media_type, p.filename,
               p.thumbnail_path, p.preview_path, p.likes, p.created_at,
               COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username
        FROM posts_fts
        JOIN posts p ON posts_fts.rowid = p.id
        LEFT JOIN users u ON u.id = p.user_id
        WHERE posts_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit)
    ).fetchall()

    return results


def search_users(conn: sqlite3.Connection, query: str, limit: int = 20) -> List[sqlite3.Row]:
    """
    搜索用户（用户名、昵称、简介）

    Args:
        conn: 数据库连接
        query: 搜索关键词
        limit: 返回数量限制

    Returns:
        匹配的用户列表
    """
    if not query or not query.strip():
        return []

    results = conn.execute(
        """
        SELECT u.id, u.username, u.display_name, u.bio, u.avatar_path, u.created_at,
               (SELECT COUNT(*) FROM posts WHERE user_id = u.id) as post_count
        FROM users_fts
        JOIN users u ON users_fts.rowid = u.id
        WHERE users_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit)
    ).fetchall()

    return results


def search_all(conn: sqlite3.Connection, query: str) -> Tuple[List[sqlite3.Row], List[sqlite3.Row]]:
    """
    同时搜索帖子和用户

    Returns:
        (posts, users) 元组
    """
    posts = search_posts(conn, query, limit=10)
    users = search_users(conn, query, limit=5)
    return posts, users
