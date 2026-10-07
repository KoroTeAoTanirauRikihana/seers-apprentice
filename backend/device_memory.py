"""Anonymous, device/browser-based memory for this public app - built
2026-08-31 per Koro's own confirmed design: most visitors never create a
real account (see patient_store.py's own signup flow, which requires an
email and password), so this gives every anonymous visitor real, permanent,
personal memory too - keyed to a device-generated ID the frontend sends
with every /ask call, no email or password required.

Mirrors the same real, tested design already proven in Koro Global Hub's
own core/apprentice_memory.py (device_id + person_name compound identity,
because anyone can share a phone) - reimplemented standalone here since
this backend deliberately never imports the private Hub's code (same
"public apps are self-contained" rule as everything else in this repo).
Reuses patient_store.py's own local sqlite file and Fernet/keyring
encryption rather than inventing a second storage/encryption scheme in the
same small app.

REAL, HARD DISTINCTION - same as the Hub's own module:
  - Nothing is ever deleted or expired from device_memory. Every exchange,
    forever, for every device, is a permanent record.
  - recall()'s max_turns is a prompt-injection cap only - how much of that
    permanent history fits in one real LLM call. It never deletes or hides
    data from the store itself.

DEVICE + NAME DISAMBIGUATION: person_name="" is the valid "no name given
yet" bucket - every new device starts here, and it's the permanent
fallback if a person never gives a name at all. When a device offers a
name that isn't already known for it, that's treated as a genuinely
separate person sharing the device - its own empty memory thread, never
blended with anyone else who has used that device.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

import patient_store

MAX_TURNS_DEFAULT = 20

# Real, durable, human-readable mirror of every exchange - added
# 2026-09-01 per Koro's own words: "they should have all their own
# informations in their own obsidians" and "they should never get lost
# in their own information." This file is a VISIBILITY copy only - it is
# never read back into a prompt. The bounded, recency-capped SQLite
# recall above (recall(), max_turns) stays the only thing that actually
# feeds an answer, so this markdown file can grow forever, for years,
# without any risk of an apprentice "getting lost" in its own history the
# way a naive whole-file-dump would cause.
VAULT_ROOT = Path.home() / "Documents" / "Norse_Celtic_Apprentice_Vault"
VAULT_LOG_PATH = VAULT_ROOT / "People and Conversations.md"


def _mirror_to_vault(person_name: str, question: str, answer: str) -> None:
    try:
        VAULT_ROOT.mkdir(parents=True, exist_ok=True)
        if not VAULT_LOG_PATH.exists():
            VAULT_LOG_PATH.write_text(
                "---\nstatus: active\ntype: memory-log\n---\n\n"
                "# People and Conversations\n\n"
                "Real, permanent, append-only record of every real person "
                "this apprentice has ever spoken with and what was actually "
                "said. This is a visibility copy for Koro only - the app's "
                "own bounded, recency-capped memory (never this whole file) "
                "is what actually informs each answer, so this file can grow "
                "forever safely.\n\n",
                encoding="utf-8",
            )
        who = (person_name or "").strip() or "Unnamed visitor"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = (
            f"### {who} \u2014 {timestamp}\n\n"
            f"**They asked:** {question.strip()}\n\n"
            f"**I answered:** {answer.strip()}\n\n---\n\n"
        )
        with VAULT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(entry)
    except OSError:
        pass  # A vault-write failure must never break a real answer.


def _connect():
    return patient_store._connect()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                person_name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL,
                content_encrypted BLOB NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_device_memory_lookup "
            "ON device_memory(device_id, person_name, id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_known_people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                person_name TEXT NOT NULL,
                first_seen_at REAL NOT NULL,
                last_seen_at REAL NOT NULL,
                UNIQUE(device_id, person_name)
            )
            """
        )


init_db()


# ---------------------------------------------------------------------------
# Low-level storage primitives
# ---------------------------------------------------------------------------

def remember(device_id: str, person_name: str, role: str, content: str) -> None:
    device_id = (device_id or "").strip()
    if not device_id:
        return
    person_name = (person_name or "").strip()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO device_memory (device_id, person_name, role, content_encrypted, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (device_id, person_name, role, patient_store._encrypt(content), time.time()),
        )


def recall(device_id: str, person_name: str = "", max_turns: int = MAX_TURNS_DEFAULT) -> list[dict]:
    device_id = (device_id or "").strip()
    if not device_id:
        return []
    person_name = (person_name or "").strip()
    limit = max(1, int(max_turns)) * 2
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content_encrypted, created_at FROM device_memory "
            "WHERE device_id=? AND person_name=? ORDER BY id DESC LIMIT ?",
            (device_id, person_name, limit),
        ).fetchall()
    history = [{"role": r, "content": patient_store._decrypt(c), "at": t} for r, c, t in rows]
    history.reverse()
    return history


def has_any_memory(device_id: str) -> bool:
    device_id = (device_id or "").strip()
    if not device_id:
        return False
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM device_memory WHERE device_id=? LIMIT 1", (device_id,)).fetchone()
    return row is not None


def recall_summary(device_id: str, person_name: str = "") -> str:
    device_id = (device_id or "").strip()
    if not device_id:
        return ""
    person_name = (person_name or "").strip()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*), MIN(created_at) FROM device_memory "
            "WHERE device_id=? AND person_name=? AND role='user'",
            (device_id, person_name),
        ).fetchone()
    turns = int(row[0] or 0)
    if not turns:
        return ""
    first_date = datetime.fromtimestamp(row[1]).date().isoformat() if row[1] else ""
    who = person_name or "this person"
    plural = "" if turns == 1 else "s"
    return f"You have spoken with {who} {turns} time{plural} before, first on {first_date}."


def note_person_seen(device_id: str, person_name: str) -> None:
    device_id = (device_id or "").strip()
    person_name = (person_name or "").strip()
    if not device_id or not person_name:
        return
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO device_known_people (device_id, person_name, first_seen_at, last_seen_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(device_id, person_name) DO UPDATE SET last_seen_at=excluded.last_seen_at",
            (device_id, person_name, now, now),
        )


def known_people(device_id: str) -> list[str]:
    device_id = (device_id or "").strip()
    if not device_id:
        return []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT person_name FROM device_known_people WHERE device_id=? ORDER BY last_seen_at DESC",
            (device_id,),
        ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Name extraction (best-effort heuristic, same as the Hub's own module)
# ---------------------------------------------------------------------------

_SELF_ID_PATTERN = re.compile(
    r"\b(?:my name is|i am|i'm|im|call me|this is|it's|its)\s+"
    r"([A-Z][a-zA-Z'\-]{1,20}(?:\s+[A-Z][a-zA-Z'\-]{1,20}){0,2})\b",
    re.IGNORECASE,
)
_NON_NAME_WORDS = {
    "fine", "good", "great", "ok", "okay", "well", "here", "asking",
    "wondering", "trying", "looking", "not", "just", "also", "still",
    "sure", "sorry", "happy", "sad", "excited", "curious", "new", "back",
    "confused", "worried", "hoping", "going", "coming", "done", "ready",
    "interested", "glad", "afraid", "unsure", "certain", "the", "a", "an",
    "having", "feeling", "in", "on", "at", "about", "from",
}


def extract_self_identification(text: str) -> str | None:
    if not text:
        return None
    match = _SELF_ID_PATTERN.search(text)
    if not match:
        return None
    candidate = match.group(1).strip()
    if candidate.split()[0].lower() in _NON_NAME_WORDS:
        return None
    return candidate


# ---------------------------------------------------------------------------
# High-level orchestration - the one call /ask needs, before and after
# ---------------------------------------------------------------------------

def build_memory_context(device_id: str, question: str, max_turns: int = MAX_TURNS_DEFAULT) -> dict:
    device_id = (device_id or "").strip()
    if not device_id:
        return {"active": False, "person_name": "", "is_new_person": False, "prompt_section": ""}

    known = known_people(device_id)
    stated = extract_self_identification(question)

    if stated:
        person_name = stated
    elif known:
        person_name = known[0]
    else:
        person_name = ""

    history = recall(device_id, person_name, max_turns=max_turns)
    ever_any = has_any_memory(device_id)
    is_new_person = not history and person_name not in known

    sections: list[str] = []
    if not ever_any:
        sections.append(
            "You have never spoken with whoever is using this device before. "
            "Naturally and warmly ask for their name early in your answer, so "
            "you can remember them personally next time - keep it "
            "conversational, not like a rigid form. Also notice if they offer "
            "their name unprompted anywhere in their own message."
        )
    else:
        if len(known) > 1 and not stated:
            others = ", ".join(known)
            sections.append(
                f"This device has been used before by more than one person you "
                f"know ({others}). Unless this message says otherwise, treat "
                f"this as {person_name}, based on the most recent conversation "
                "on this device - but if they identify themselves with a "
                "different name, treat them as that separate person instead, "
                "with their own separate memory."
            )
        if history:
            summary = recall_summary(device_id, person_name)
            transcript = "\n".join(
                f"{'This person' if row['role'] == 'user' else 'You'}: {row['content']}"
                for row in history
            )
            who = person_name or "this person"
            sections.append(
                "Real prior conversation history with this specific person "
                f"(for continuity only):\n{summary}\n\nWith {who}:\n{transcript}"
            )
        elif is_new_person and stated and known:
            sections.append(
                f"{stated} is a new person on this device you haven't spoken "
                f"with before under that name, even though this device has "
                f"been used by someone else before ({', '.join(known)}). Keep "
                f"their memory separate."
            )

    prompt_section = "\n\n".join(section for section in sections if section)
    if prompt_section:
        prompt_section += "\n\n---\n\n"

    return {
        "active": True,
        "person_name": person_name,
        "is_new_person": is_new_person,
        "prompt_section": prompt_section,
    }


def remember_exchange(device_id: str, person_name: str, question: str, answer: str) -> None:
    device_id = (device_id or "").strip()
    if not device_id:
        return
    person_name = (person_name or "").strip()
    remember(device_id, person_name, "user", question)
    remember(device_id, person_name, "assistant", answer)
    if person_name:
        note_person_seen(device_id, person_name)
    _mirror_to_vault(person_name, question, answer)
