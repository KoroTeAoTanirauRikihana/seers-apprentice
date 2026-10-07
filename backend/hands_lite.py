r"""HANDS, LITE - so a public apprentice app writes in its own Obsidian and never forgets a face.

Koro, 2026-09-15: "give everyone hands so they can write" / "everybody remembers
every interaction with everyone, like the tohunga never forgets a face" /
"everyone is supposed to write their own in their own obsidian".

The 133 public apps are their own processes and never import the Hub core, so
this is a copy of the one thing they need from core/hands.py, with no imports
outside the standard library. It is placed beside each app's app.py by
give_everyone_hands.py. The vault is the app's own: sync_knowledge.SOURCE is
`<vault>\Knowledge`, so the vault root is its parent.

  daily(line)                         -> <vault>\YYYY-MM-DD.md, "## Today, as it happened"
  remember_face(who, what, said="")   -> <vault>\Faces\<who>.md + "Everyone I have met.md"

Never raises. A real person has no vault of their own here; the apprentice
remembers them. For a signed-in patient/client (a user_id) only "we spoke" is
written - what was said stays in the app's own store, not in a plain file.
"""
from __future__ import annotations

import re
import threading
from datetime import date, datetime
from pathlib import Path

_LOCK = threading.Lock()


def _vault() -> Path | None:
    try:
        import sync_knowledge  # the app's own, beside this file
        src = Path(getattr(sync_knowledge, "SOURCE", ""))
        v = src.parent if src.name.lower() == "knowledge" else src
        return v if v.is_dir() else None
    except Exception:  # noqa: BLE001
        return None


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _\-.']+", "-", str(s)).strip(" -.")[:80] or "someone"


def _append(path: Path, text: str) -> None:
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)


def daily(line: str) -> bool:
    try:
        v = _vault()
        if v is None:
            return False
        note = v / f"{date.today().isoformat()}.md"
        head = ""
        if not note.is_file():
            head = f"# {date.today().isoformat()}\n\n## Today, as it happened\n\n"
        elif "## Today, as it happened" not in note.read_text(encoding="utf-8", errors="replace"):
            head = "\n## Today, as it happened\n\n"
        _append(note, head + f"- {datetime.now():%H:%M} {line.strip()}\n")
        return True
    except Exception:  # noqa: BLE001
        return False


def remember_face(who: str, what: str, said: str = "") -> bool:
    try:
        v = _vault()
        if v is None or not str(who).strip():
            return False
        name = _safe(who)
        face = v / "Faces" / f"{name}.md"
        if not face.is_file():
            _append(face, f"# {name}\n\nFirst met {date.today().isoformat()}. I do not forget a face.\n\n")
            index = v / "Everyone I have met.md"
            head = ("# Everyone I have met\n\nOne line per face, the day we first met; each has their own note in `Faces\\`. "
                    "Koro, 2026-09-15: \"everybody remembers every interaction with everyone, like the tohunga never forgets a face.\"\n\n"
                    if not index.is_file() else "")
            _append(index, head + f"- {date.today().isoformat()} [[Faces/{name}|{name}]] - {what.strip()[:120]}\n")
        entry = f"## {datetime.now():%Y-%m-%d %H:%M} - {what.strip()}\n\n"
        if said:
            entry += said.strip()[:1500] + "\n\n"
        _append(face, entry)
        return True
    except Exception:  # noqa: BLE001
        return False
