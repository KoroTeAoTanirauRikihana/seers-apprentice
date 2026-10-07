"""Copies the current Seer's Apprentice knowledge base out of its own
dedicated vault (Norse_Celtic_Apprentice_Vault - separate from Koro's
personal Obsidian vault, built 2026-08-28) into this standalone project's
own knowledge/ folder, so the public app's backend never has a live path
dependency into Koro's own machine - it only ever reads a
deliberately-synced, filtered snapshot. Same pattern as the Tohunga's
Apprentice Public App's own sync_knowledge.py.

Real filtering, not a blind copy - reuses the same honesty-tier vocabulary
already used consistently across every Norse/Celtic knowledge document
(see workers/norse_celtic_apprentice_research.py's SYSTEM_PROMPT): "High
confidence", "Solid but singular-source", "Genuinely debated", etc. are
all real, cited claims - kept. "Gap - flagged rather than filled with
assumption" and "Lower confidence" are dropped before anything reaches the
public app.

Called two ways: as a one-off CLI script (`python sync_knowledge.py`), and
imported by app.py's background refresh thread for the automatic periodic
sync (same pattern Koro asked for on the Maori side, 2026-08-27:
"make it refresh by itself only verified information to keep the app
honest").
"""
from __future__ import annotations

import re
from pathlib import Path

SOURCE = (
    Path.home()
    / "Documents"
    / "Norse_Celtic_Apprentice_Vault"
    / "Knowledge"
)
DEST = Path(__file__).resolve().parent / "knowledge"

_UNVERIFIED_MARKERS = (
    re.compile(r"gap\s*[-—]\s*flagged", re.IGNORECASE),
    re.compile(r"lower confidence", re.IGNORECASE),
)


def _is_verified_paragraph(paragraph: str) -> bool:
    return not any(marker.search(paragraph) for marker in _UNVERIFIED_MARKERS)


def _filter_verified(text: str) -> str:
    paragraphs = re.split(r"\n\s*\n", text)
    kept = [p for p in paragraphs if _is_verified_paragraph(p)]
    return "\n\n".join(kept)


def sync() -> dict:
    """Real return value used by both the CLI entry point and app.py's
    background refresh thread, so both report the same real counts.

    Recursive, and preserves the vault's real Foundations/Norse-Specific/
    Celtic-Specific/Clan-Specific folder structure rather than flattening
    everything."""
    if not SOURCE.is_dir():
        raise FileNotFoundError(f"Source knowledge folder not found: {SOURCE}")
    DEST.mkdir(parents=True, exist_ok=True)
    for old in DEST.glob("**/*.md"):
        old.unlink()

    synced_files = 0
    dropped_paragraphs = 0
    for path in sorted(SOURCE.glob("**/*.md")):
        original = path.read_text(encoding="utf-8")
        filtered = _filter_verified(original)
        dropped_paragraphs += len(re.split(r"\n\s*\n", original)) - len(
            re.split(r"\n\s*\n", filtered)
        )
        relative = path.relative_to(SOURCE)
        dest_path = DEST / relative
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(filtered, encoding="utf-8")
        synced_files += 1

    return {"synced_files": synced_files, "dropped_paragraphs": dropped_paragraphs}


def main() -> None:
    result = sync()
    print(
        f"Synced {result['synced_files']} knowledge file(s) from {SOURCE} to {DEST} "
        f"(dropped {result['dropped_paragraphs']} unverified paragraph(s): "
        "gap-flagged or lower-confidence content excluded from the public app)."
    )


if __name__ == "__main__":
    main()
