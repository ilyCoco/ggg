from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Any

DB_DIR = Path("data")
DB_PATH = DB_DIR / "geshi.db"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            role TEXT DEFAULT 'user',
            department TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS kb_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            icon TEXT DEFAULT '📁',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#6B7280',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS kb_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            plain_text TEXT NOT NULL DEFAULT '',
            scene_type TEXT DEFAULT 'general',
            category_id INTEGER,
            summary_json TEXT,
            created_by INTEGER NOT NULL,
            is_public INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES kb_categories(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS entry_tags (
            entry_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (entry_id, tag_id),
            FOREIGN KEY (entry_id) REFERENCES kb_entries(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS kb_entries_fts USING fts5(
            title, plain_text, content='kb_entries', content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS kb_entries_ai AFTER INSERT ON kb_entries BEGIN
            INSERT INTO kb_entries_fts(rowid, title, plain_text)
            VALUES (new.id, new.title, new.plain_text);
        END;

        CREATE TRIGGER IF NOT EXISTS kb_entries_ad AFTER DELETE ON kb_entries BEGIN
            INSERT INTO kb_entries_fts(kb_entries_fts, rowid, title, plain_text)
            VALUES ('delete', old.id, old.title, old.plain_text);
        END;

        CREATE TRIGGER IF NOT EXISTS kb_entries_au AFTER UPDATE ON kb_entries BEGIN
            INSERT INTO kb_entries_fts(kb_entries_fts, rowid, title, plain_text)
            VALUES ('delete', old.id, old.title, old.plain_text);
            INSERT INTO kb_entries_fts(rowid, title, plain_text)
            VALUES (new.id, new.title, new.plain_text);
        END;

        -- Phase 2: Tasks & Notifications
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            assignee_id INTEGER,
            creator_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','in_progress','completed','cancelled')),
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('high','medium','low')),
            deadline TEXT DEFAULT '',
            risk_tags TEXT DEFAULT '[]',
            source_type TEXT DEFAULT 'manual' CHECK(source_type IN ('manual','meeting')),
            source_summary_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignee_id) REFERENCES users(id),
            FOREIGN KEY (creator_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('task_assigned','task_deadline','task_completed','approval_request','approval_result','message_new','meeting_reminder','system')),
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            link TEXT DEFAULT '',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- Phase 3: Approvals & Calendar
        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('leave','expense','seal','other')),
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            applicant_id INTEGER NOT NULL,
            current_approver_id INTEGER,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','cancelled')),
            approval_chain TEXT NOT NULL DEFAULT '[]',
            current_step INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (applicant_id) REFERENCES users(id),
            FOREIGN KEY (current_approver_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            creator_id INTEGER NOT NULL,
            event_type TEXT DEFAULT 'personal' CHECK(event_type IN ('meeting','task_deadline','reminder','personal')),
            start_time TEXT NOT NULL,
            end_time TEXT DEFAULT '',
            all_day INTEGER DEFAULT 0,
            location TEXT DEFAULT '',
            attendees TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users(id)
        );

        -- Phase 4: Attendance, Announcements, Messages
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            check_in TEXT DEFAULT '',
            check_out TEXT DEFAULT '',
            status TEXT DEFAULT 'normal' CHECK(status IN ('normal','late','early','absent')),
            ip_address TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_published INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id)
        );
    """)
    conn.commit()

    # Create default admin if no users exist
    cur = conn.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        _create_default_admin(conn)

    # Create default categories if none exist
    cur = conn.execute("SELECT COUNT(*) FROM kb_categories")
    if cur.fetchone()[0] == 0:
        for name, desc, icon in [
            ("会议纪要", "会议总结与待办事项", "📋"),
            ("课堂知识", "课堂笔记与知识提炼", "📖"),
            ("项目文档", "项目相关文档与记录", "📁"),
            ("规章制度", "公司制度与规范", "📜"),
            ("其他", "未分类内容", "📄"),
        ]:
            conn.execute(
                "INSERT INTO kb_categories (name, description, icon) VALUES (?, ?, ?)",
                (name, desc, icon),
            )
        conn.commit()
    conn.close()


def _create_default_admin(conn: sqlite3.Connection) -> None:
    import hashlib
    import secrets

    salt = secrets.token_hex(16)
    pw = "admin123"
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200000)
    password_hash = f"pbkdf2:sha256:200000${salt}${dk.hex()}"
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name, role, department) VALUES (?, ?, ?, ?, ?)",
        ("admin", password_hash, "系统管理员", "admin", "管理部"),
    )
    conn.commit()
