-- 举报系统数据库迁移

-- 1. 创建举报表
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    details TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    handled_by INTEGER,
    handled_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(reporter_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(handled_by) REFERENCES users(id)
);

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_target ON reports(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_reports_reporter ON reports(reporter_id);
