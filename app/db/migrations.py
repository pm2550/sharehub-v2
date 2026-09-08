"""数据库迁移系统"""

import logging
import sqlite3
from typing import List
from app.db.connection import get_db

logger = logging.getLogger("sharehub.migrations")

# 基础表 —— 原本建在老单体 app.py 的 init_db() 里。模块化重构后 main.py 只调
# run_migrations()，没人再调 init_db()，于是全新部署会在 migration 1 的
# "CREATE INDEX ON posts" 上直接失败（posts 表根本不存在）。
# 这里在跑版本化迁移之前无条件执行一遍，全部 IF NOT EXISTS，对已有库是 no-op。
BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    bio TEXT,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    media_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'upload',
    prompt TEXT,
    likes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER,
    author TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS post_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(post_id, user_id),
    FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    steps INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    started_unix INTEGER,
    finished_unix INTEGER,
    result_post_id INTEGER,
    error TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(result_post_id) REFERENCES posts(id)
);
"""

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

    # Version 17: RunPod 后端支持 — ai_jobs 增加 backend 字段 + 每日用量追踪表
    """
    ALTER TABLE ai_jobs ADD COLUMN backend TEXT DEFAULT 'local';
    CREATE TABLE IF NOT EXISTS ai_daily_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        runpod_count INTEGER DEFAULT 0,
        UNIQUE(user_id, date),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_ai_daily_usage_user_date ON ai_daily_usage(user_id, date);
    """,

    # Version 18: 资源区（云盘）— posts 增加 file_size 和 original_filename 字段
    """
    ALTER TABLE posts ADD COLUMN file_size INTEGER DEFAULT NULL;
    ALTER TABLE posts ADD COLUMN original_filename TEXT DEFAULT NULL;
    """,

    # Version 19: PM Drive 后端 — posts 增加 pmdrive_uri 字段存 Cloudreve URI
    """
    ALTER TABLE posts ADD COLUMN pmdrive_uri TEXT DEFAULT NULL;
    CREATE INDEX IF NOT EXISTS idx_posts_filename ON posts(filename);
    """,

    # Version 20: 分片上传会话 — 大文件后台上传 + 断点续传
    """
    CREATE TABLE IF NOT EXISTS upload_sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        media_type TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
        total_size INTEGER NOT NULL,
        chunk_size INTEGER NOT NULL,
        total_chunks INTEGER NOT NULL,
        received_chunks INTEGER NOT NULL DEFAULT 0,
        pmdrive_session_id TEXT DEFAULT NULL,
        pmdrive_uri TEXT DEFAULT NULL,
        tmp_path TEXT DEFAULT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'uploading',
        error TEXT DEFAULT NULL,
        post_id INTEGER DEFAULT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_upload_sessions_user ON upload_sessions(user_id, status);
    CREATE INDEX IF NOT EXISTS idx_upload_sessions_updated ON upload_sessions(updated_at);
    """,

    # Version 21: 补齐 posts.preview_path（视频循环预览片段路径）
    # 这一列历史上是直接在生产库 ALTER 加的，从没进过迁移列表 —— 生产有、
    # 全新部署没有，导致新环境一上传就 "no column named preview_path"。
    # 生产库跑到这里会因为列已存在而报 duplicate column，由 runner 容错跳过。
    """
    ALTER TABLE posts ADD COLUMN preview_path TEXT DEFAULT NULL;
    """,

    # Version 22: 补齐 idx_tags_name —— 同样是历史上手工建在生产库、
    # 从没进过迁移列表的对象（全量 schema 对比时抓出来的）
    """
    CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
    """,
]


def run_migrations(db_path: str):
    """运行所有未应用的迁移"""
    with get_db(db_path) as conn:
        # 基础表必须先于版本化迁移建好（migration 1 就要在 posts 上建索引）
        conn.executescript(BASE_SCHEMA)
        conn.commit()

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
                            if not statement:
                                continue
                            try:
                                conn.execute(statement)
                            except sqlite3.OperationalError as e:
                                # SQLite 的 ALTER TABLE ADD COLUMN 没有 IF NOT EXISTS。
                                # 列已存在 = 这条迁移的效果早就在库里（历史上手工加过），
                                # 跳过即可，不然老库一升级就起不来。
                                if "duplicate column name" in str(e).lower():
                                    logger.info("  ↷ 列已存在，跳过: %s", statement[:70])
                                else:
                                    raise

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
