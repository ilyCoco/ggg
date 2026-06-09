from __future__ import annotations

import hashlib
import secrets
import re
from typing import Any

from database import get_connection


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200000)
    return f"pbkdf2:sha256:200000${salt}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        prefix, salt, stored = password_hash.split("$")
        _, hash_name, iterations = prefix.split(":")
        dk = hashlib.pbkdf2_hmac(
            hash_name, password.encode(), salt.encode(), int(iterations)
        )
        return dk.hex() == stored
    except (ValueError, AttributeError):
        return False


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return dict(row)


def register_user(
    username: str,
    password: str,
    display_name: str = "",
    email: str = "",
    department: str = "",
) -> tuple[bool, str]:
    if not re.match(r"^[a-zA-Z0-9_一-龥]{2,30}$", username):
        return False, "用户名需为 2-30 位中英文、数字或下划线"
    if len(password) < 6:
        return False, "密码至少需要 6 位"
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        conn.close()
        return False, "用户名已存在"
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, email, department) VALUES (?, ?, ?, ?, ?)",
            (username, hash_password(password), display_name or username, email, department),
        )
        conn.commit()
        conn.close()
        return True, "注册成功"
    except Exception as e:
        conn.close()
        return False, f"注册失败：{e}"


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users() -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, display_name, email, role, department, is_active, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user(
    user_id: int,
    display_name: str | None = None,
    email: str | None = None,
    department: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> bool:
    conn = get_connection()
    fields = []
    values: list[Any] = []
    if display_name is not None:
        fields.append("display_name = ?")
        values.append(display_name)
    if email is not None:
        fields.append("email = ?")
        values.append(email)
    if department is not None:
        fields.append("department = ?")
        values.append(department)
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(1 if is_active else 0)
    if password:
        fields.append("password_hash = ?")
        values.append(hash_password(password))
    if not fields:
        conn.close()
        return False
    values.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True
