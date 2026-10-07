"""Real, encrypted per-patient account and conversation storage for
United Kingdom - The Seer's Apprentice's public app.

Built 2026-08-30, generalized from the pattern first built for The
Doctor's Apprentice - Koro's own instruction: "build it for each
apprentice so they work properly," after asking whether any apprentice
remembers who it's talking to. Same real architecture across every
apprentice that has it:

- Real accounts (email + password, hashed with werkzeug's
  generate_password_hash/check_password_hash - salted, standard, never
  plaintext).
- Real field-level encryption of every stored message (Fernet symmetric
  encryption, key generated once and stored in Windows Credential
  Manager via `keyring` under this app's own service name - same secure
  pattern already used for this app's OpenAI key - never written to disk
  in plaintext or committed to source control).
- Real conversation memory: stores the actual conversation turns (not an
  auto-extracted "profile") and replays recent history back into context
  on each new question - honest and inspectable, never a silently
  hallucinated summary standing in for what someone actually said.
- Real right to erasure: `delete_user` removes the account and every
  stored message permanently - no soft-delete, no retained backup.

Local SQLite database (`patients.db`, gitignored, never committed).
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "patients.db"

KEYRING_SERVICE_NAME = "SeersApprenticeApp"
ENV_KEY_NAME = "SEERSAPPRENTICEAPP_DB_KEY"

MAX_HISTORY_MESSAGES = 20  # real cap so context can't grow unbounded
SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 30  # 30 real days


def _load_or_create_encryption_key() -> bytes:
    from_env = os.environ.get(ENV_KEY_NAME, "")
    if from_env:
        return from_env.encode("utf-8")
    try:
        import keyring

        existing = keyring.get_password(KEYRING_SERVICE_NAME, "db_encryption_key")
        if existing:
            return existing.encode("utf-8")
        new_key = Fernet.generate_key().decode("utf-8")
        keyring.set_password(KEYRING_SERVICE_NAME, "db_encryption_key", new_key)
        return new_key.encode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Could not load or create a real encryption key via keyring - "
            "refusing to store patient data unencrypted."
        ) from exc


_FERNET = Fernet(_load_or_create_encryption_key())


def _encrypt(text: str) -> bytes:
    return _FERNET.encrypt(text.encode("utf-8"))


def _decrypt(blob: bytes) -> str:
    try:
        return _FERNET.decrypt(blob).decode("utf-8")
    except InvalidToken:
        return "[unreadable - encryption key mismatch]"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                consented_at REAL NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content_encrypted BLOB NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )


init_db()


class AccountError(Exception):
    pass


def create_user(email: str, password: str, consent: bool) -> int:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise AccountError("A real email address is required.")
    if len(password) < 8:
        raise AccountError("Password must be at least 8 characters.")
    if not consent:
        raise AccountError(
            "Real, explicit consent to store your conversation data (encrypted) is required to create an account."
        )
    password_hash = generate_password_hash(password)
    now = time.time()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, consented_at, created_at) VALUES (?, ?, ?, ?)",
                (email, password_hash, now, now),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise AccountError("An account with that email already exists.") from exc


def authenticate_user(email: str, password: str) -> int:
    email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    if not row or not check_password_hash(row[1], password):
        raise AccountError("Incorrect email or password.")
    return row[0]


def delete_user(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, now + SESSION_LIFETIME_SECONDS),
        )
    return token


def resolve_session(token: str) -> int | None:
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    if not row or row[1] < time.time():
        return None
    return row[0]


def destroy_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def save_message(user_id: int, role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (user_id, role, content_encrypted, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, _encrypt(content), time.time()),
        )


def get_recent_history(user_id: int, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content_encrypted, created_at FROM messages "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    history = [{"role": role, "content": _decrypt(blob), "at": at} for role, blob, at in rows]
    history.reverse()
    return history
