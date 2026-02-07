-- 关注系统数据库迁移

-- 1. 创建关注表
CREATE TABLE IF NOT EXISTS follows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_id INTEGER NOT NULL,
    followed_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(follower_id, followed_id),
    FOREIGN KEY(follower_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(followed_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK(follower_id != followed_id)
);

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_follows_follower ON follows(follower_id);
CREATE INDEX IF NOT EXISTS idx_follows_followed ON follows(followed_id);
