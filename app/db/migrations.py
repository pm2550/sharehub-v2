"""数据库迁移系统"""

import logging
from typing import List
from app.db.connection import get_db

logger = logging.getLogger("sharehub.migrations")

# 迁移列表 - 每个字符串是一个版本的 SQL 语句集合
MIGRATIONS: List[str] = [
    # Version 1: 基础表索引
    """
    CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id);
    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
    CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source);
    CREATE INDEX IF NOT EXISTS idx_posts_media_type ON posts(media_type);
    CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
    CREATE INDEX IF NOT EXISTS idx_comments_user_id ON comments(user_id);
    CREATE INDEX IF NOT EXISTS idx_post_likes_post_id ON post_likes(post_id);
    CREATE INDEX IF NOT EXISTS idx_post_likes_user_id ON post_likes(user_id);
    CREATE INDEX IF NOT EXISTS idx_ai_jobs_user_id ON ai_jobs(user_id);
    CREATE INDEX IF NOT EXISTS idx_ai_jobs_status ON ai_jobs(status);
    """,

    # Version 2: 用户增强字段
    """
    ALTER TABLE users ADD COLUMN avatar_path TEXT DEFAULT NULL;
    ALTER TABLE users ADD COLUMN theme_preference TEXT DEFAULT 'system';
    """,

    # Version 3: 帖子增强字段
    """
    ALTER TABLE posts ADD COLUMN thumbnail_path TEXT DEFAULT NULL;
    ALTER TABLE posts ADD COLUMN media_width INTEGER DEFAULT NULL;
    ALTER TABLE posts ADD COLUMN media_height INTEGER DEFAULT NULL;
    """,

    # Version 4: AI 任务增强字段
    """
    ALTER TABLE ai_jobs ADD COLUMN retry_count INTEGER DEFAULT 0;
    ALTER TABLE ai_jobs ADD COLUMN cancelled INTEGER DEFAULT 0;
    ALTER TABLE ai_jobs ADD COLUMN error_message TEXT DEFAULT NULL;
    ALTER TABLE ai_jobs ADD COLUMN sampler TEXT DEFAULT 'Euler a';
    ALTER TABLE ai_jobs ADD COLUMN cfg_scale REAL DEFAULT 7.0;
    ALTER TABLE ai_jobs ADD COLUMN denoising_strength REAL DEFAULT NULL;
    """,

    # Version 5: 标签系统
    """
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL COLLATE NOCASE,
        usage_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS post_tags (
        post_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (post_id, tag_id),
        FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
        FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_post_tags_tag_id ON post_tags(tag_id);
    CREATE INDEX IF NOT EXISTS idx_tags_slug ON tags(slug);
    CREATE INDEX IF NOT EXISTS idx_tags_usage_count ON tags(usage_count DESC);
    """,

    # Version 6: 关注系统
    """
    CREATE TABLE IF NOT EXISTS follows (
        follower_id INTEGER NOT NULL,
        followed_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (follower_id, followed_id),
        FOREIGN KEY(follower_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(followed_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_follows_followed ON follows(followed_id);
    CREATE INDEX IF NOT EXISTS idx_follows_follower ON follows(follower_id);
    """,

    # Version 7: 通知系统
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        source_user_id INTEGER DEFAULT NULL,
        post_id INTEGER DEFAULT NULL,
        comment_id INTEGER DEFAULT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(source_user_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
        FOREIGN KEY(comment_id) REFERENCES comments(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(user_id, is_read);
    CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);
    """,

    # Version 8: 举报系统
    """
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER NOT NULL,
        post_id INTEGER DEFAULT NULL,
        comment_id INTEGER DEFAULT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        reviewed_by INTEGER DEFAULT NULL,
        reviewed_at TEXT DEFAULT NULL,
        action_taken TEXT DEFAULT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(reporter_id) REFERENCES users(id),
        FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
        FOREIGN KEY(comment_id) REFERENCES comments(id) ON DELETE CASCADE,
        FOREIGN KEY(reviewed_by) REFERENCES users(id)
    );
    CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
    CREATE INDEX IF NOT EXISTS idx_reports_post_id ON reports(post_id);
    CREATE INDEX IF NOT EXISTS idx_reports_comment_id ON reports(comment_id);
    """,

    # Version 9: FTS5 全文搜索
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
        title, description, content='posts', content_rowid='id'
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS users_fts USING fts5(
        username, display_name, bio, content='users', content_rowid='id'
    );
    """,

    # Version 10: FTS5 同步触发器
    """
    CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts
    BEGIN
        INSERT INTO posts_fts(rowid, title, description)
        VALUES (new.id, new.title, COALESCE(new.description, ''));
    END;

    CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts
    BEGIN
        INSERT INTO posts_fts(posts_fts, rowid, title, description)
        VALUES ('delete', old.id, old.title, COALESCE(old.description, ''));
    END;

    CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts
    BEGIN
        INSERT INTO posts_fts(posts_fts, rowid, title, description)
        VALUES ('delete', old.id, old.title, COALESCE(old.description, ''));
        INSERT INTO posts_fts(rowid, title, description)
        VALUES (new.id, new.title, COALESCE(new.description, ''));
    END;

    CREATE TRIGGER IF NOT EXISTS users_ai AFTER INSERT ON users
    BEGIN
        INSERT INTO users_fts(rowid, username, display_name, bio)
        VALUES (new.id, new.username, COALESCE(new.display_name, new.username), COALESCE(new.bio, ''));
    END;

    CREATE TRIGGER IF NOT EXISTS users_ad AFTER DELETE ON users
    BEGIN
        INSERT INTO users_fts(users_fts, rowid, username, display_name, bio)
        VALUES ('delete', old.id, old.username, COALESCE(old.display_name, old.username), COALESCE(old.bio, ''));
    END;

    CREATE TRIGGER IF NOT EXISTS users_au AFTER UPDATE ON users
    BEGIN
        INSERT INTO users_fts(users_fts, rowid, username, display_name, bio)
        VALUES ('delete', old.id, old.username, COALESCE(old.display_name, old.username), COALESCE(old.bio, ''));
        INSERT INTO users_fts(rowid, username, display_name, bio)
        VALUES (new.id, new.username, COALESCE(new.display_name, new.username), COALESCE(new.bio, ''));
    END;
    """,

    # Version 11: 用户保存的 Prompt
    """
    CREATE TABLE IF NOT EXISTS user_prompts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        prompt TEXT NOT NULL,
        negative_prompt TEXT DEFAULT '',
        steps INTEGER DEFAULT 40,
        width INTEGER DEFAULT 768,
        height INTEGER DEFAULT 1024,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_user_prompts_user_id ON user_prompts(user_id);
    """,

    # Version 12: AI 任务优先级字段
    """
    ALTER TABLE ai_jobs ADD COLUMN priority INTEGER DEFAULT 0;
    """,

    # Version 13: 收藏/书签系统
    """
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        post_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, post_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
    CREATE INDEX IF NOT EXISTS idx_favorites_post_id ON favorites(post_id);
    """,

    # Version 14: 私信系统
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
    CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id);
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(receiver_id, is_read);
    """,

    # Version 15: Following Feed 优化索引
    """
    CREATE INDEX IF NOT EXISTS idx_posts_user_created ON posts(user_id, created_at DESC);
    """,

    # Version 16: 私信支持附带帖子卡片
    """
    ALTER TABLE messages ADD COLUMN post_id INTEGER DEFAULT NULL REFERENCES posts(id) ON DELETE SET NULL;
    """,
]


def run_migrations(db_path: str):
    """运行所有未应用的迁移"""
    with get_db(db_path) as conn:
        # 创建版本追踪表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

        # 获取当前版本
        row = conn.execute("SELECT MAX(version) as v FROM _schema_version").fetchone()
        current_version = row["v"] if row["v"] is not None else 0

        logger.info(f"Current schema version: {current_version}")

        # 应用新迁移
        for i, sql in enumerate(MIGRATIONS, start=1):
            if i > current_version:
                logger.info(f"Applying migration {i}...")
                try:
                    # 对于包含触发器的语句，直接执行整块SQL
                    if "CREATE TRIGGER" in sql:
                        conn.executescript(sql.strip())
                    else:
                        # 分号分隔的多条语句
                        for statement in sql.strip().split(";"):
                            statement = statement.strip()
                            if statement:
                                conn.execute(statement)

                    # 记录版本
                    conn.execute(
                        "INSERT INTO _schema_version (version) VALUES (?)", (i,)
                    )
                    conn.commit()
                    logger.info(f"✓ Migration {i} applied successfully")
                except Exception as e:
                    logger.error(f"✗ Migration {i} failed: {e}")
                    raise

        logger.info(f"All migrations applied. Current version: {len(MIGRATIONS)}")
