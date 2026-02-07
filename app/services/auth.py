"""用户认证服务"""

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional


class ValidationError(Exception):
    """认证验证错误"""
    pass


def now_iso() -> str:
    """返回当前UTC时间的ISO格式字符串"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    使用 PBKDF2-HMAC-SHA256 哈希密码

    Args:
        password: 明文密码
        salt: 可选的十六进制盐值，不提供则随机生成

    Returns:
        格式为 "{salt}${digest}" 的哈希字符串
    """
    raw_salt = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, 120_000)
    return f"{raw_salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """
    验证密码

    Args:
        password: 待验证的明文密码
        stored: 存储的哈希字符串

    Returns:
        密码是否匹配
    """
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False

    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored)


def register_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    """
    注册新用户

    Args:
        conn: 数据库连接
        username: 用户名
        password: 明文密码

    Returns:
        新用户的ID

    Raises:
        ValidationError: 验证失败
    """
    username = username.strip()

    # 验证用户名长度
    if len(username) < 3 or len(username) > 32:
        raise ValidationError("用户名长度需在 3-32")

    # 验证密码长度
    if len(password) < 6:
        raise ValidationError("密码至少 6 位")

    # 检查用户名是否已存在
    existing = conn.execute(
        "SELECT 1 FROM users WHERE username = ?", (username,)
    ).fetchone()

    if existing:
        raise ValidationError("用户名已存在")

    # 创建用户
    password_hash = hash_password(password)
    conn.execute(
        """
        INSERT INTO users(username, display_name, password_hash, is_admin, created_at)
        VALUES (?, ?, ?, 0, ?)
        """,
        (username, username, password_hash, now_iso()),
    )

    # 获取新用户ID
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 如果这是第一个用户，自动设为管理员
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 1:
        conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))

    return int(user_id)


def authenticate_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    """
    验证用户凭据并返回用户ID

    Args:
        conn: 数据库连接
        username: 用户名
        password: 明文密码

    Returns:
        用户ID

    Raises:
        ValidationError: 用户名或密码错误
    """
    user = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()

    if not user or not verify_password(password, user["password_hash"]):
        raise ValidationError("用户名或密码错误")

    return int(user["id"])


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    """根据ID获取用户信息"""
    return conn.execute(
        "SELECT id, username, display_name, bio, avatar_path, is_admin, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def get_user_by_username(
    conn: sqlite3.Connection, username: str
) -> Optional[sqlite3.Row]:
    """根据用户名获取用户信息"""
    return conn.execute(
        "SELECT id, username, display_name, bio, avatar_path, is_admin, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()


def update_profile(
    conn: sqlite3.Connection, user_id: int, display_name: str, bio: str
):
    """更新用户资料"""
    conn.execute(
        "UPDATE users SET display_name = ?, bio = ? WHERE id = ?",
        (display_name.strip(), bio.strip()[:500], user_id),
    )


def update_password(conn: sqlite3.Connection, user_id: int, new_password: str):
    """更新用户密码"""
    password_hash = hash_password(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
    )
