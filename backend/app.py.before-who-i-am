"""The Seer's Apprentice - standalone public backend.

Deliberately separate from Koro Global Hub (same reasoning as the Tohunga's
Apprentice Public App and the Cultural Check Agent): the Hub holds Koro's
private tasks, family info, and other workers, none of which should ever
face the public internet. This service does exactly one thing - answer
questions from the same Norse/Celtic knowledge base the private Hub worker
(workers/norse_celtic_apprentice.py) uses, with the same "apprentice,
never claims a real tradition-holder title" honesty rules baked in - and
nothing else. It has no access to the Hub, the vault, or any of Koro's
other systems.

Knowledge is a deliberately-synced snapshot (see sync_knowledge.py), never
a live read of Koro's personal machine - this process should be safely
deployable to a public host with zero path dependency on his own machine.

Real, honest cost note (read before deploying this publicly): every /ask
call makes one real, paid OpenAI API call. MAX_REQUESTS_PER_DAY below is a
blunt, real safeguard against unbounded spend from public traffic - raise
it deliberately once real usage and real cost are being watched, not
before.
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from openai import OpenAI

import device_memory
import patient_store
import sync_knowledge

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"


def _load_api_key() -> str:
    """Real deployment (Render/Railway/etc) should always set OPENAI_API_KEY
    as a real environment variable. Falls back to Windows Credential Manager
    (via keyring) only for local development on Koro's own machine, so the
    raw key never has to sit in a plaintext .env file even for local
    testing. Deliberately its own funded key, not shared with the Tohunga's
    Apprentice app - public traffic on two separate apps is unpredictable
    cost that shouldn't be silently pooled."""
    from_env = os.environ.get("OPENAI_API_KEY", "")
    if from_env:
        return from_env
    try:
        import keyring

        from_keyring = keyring.get_password("SeersApprenticeApp", "openai_api_key")
        return from_keyring or ""
    except Exception:
        return ""


OPENAI_API_KEY = _load_api_key()
MODEL = os.environ.get("SEERS_APPRENTICE_MODEL", "gpt-4o-mini")

MAX_REQUESTS_PER_DAY_PER_IP = int(os.environ.get("MAX_REQUESTS_PER_DAY_PER_IP", "40"))
_request_log: dict[str, list[float]] = defaultdict(list)

APP_NAME = "The Seer's Apprentice"

DISCLAIMER = (
    "I'm the Seer's Apprentice - I carry real, sourced research about Norse "
    "and Celtic tradition (mythology, runes, Clan Gunn history, craft, "
    "medicine, ritual, and more), but I'm not a druid, skald, filí, bard, "
    "völva, or goði, and I never claim to be. Where popular symbols or "
    "practices are later folklore rather than historical-period tradition "
    "(the vegvísir, blue woad tattoos, and Victorian tartan revival are "
    "real examples), I say so plainly instead of presenting them as "
    "ancient. Treat what I say as a well-sourced starting point, not "
    "lived spiritual or clan authority."
)

SYSTEM_PROMPT = f"""
You are {APP_NAME} - a free, public knowledge-consultation assistant
carrying deeply researched, real, sourced knowledge about Norse and Celtic
tradition: cosmology (Yggdrasil, the Nine Worlds), runes, knowledge-keeper
roles (skald, völva, goði/gyðja, druid, filí, bard), Clan Gunn and the
Norse-Gael world, tattoo/body-marking history, medicine, prayer and
sacrifice, craft (carving, shipbuilding), astronomy/navigation, oratory
and law-speaking, food and farming, war rites, death rites, weaving, and
prophecy/seership.

CRITICAL, NEVER DROP: you are an apprentice, never a druid, skald, filí,
bard, völva, goði, gyðja, or any other master-practitioner or
tradition-holder title. You carry researched, historical/academic
knowledge, not lived spiritual or clan authority. On anything genuinely
personal or consequential to a real questioner - their own specific
family/clan lineage, how to actually combine traditions in a real worn
design or ritual - say plainly that real authority belongs to real people:
family elders, relevant clan/heritage societies, and qualified
practitioners in the living tradition - never invented or assumed by you.

CRITICAL, ON HONESTY: several popular "Viking" or "Celtic" symbols and
practices in wide circulation are later folklore or modern revival, not
the original historical-period tradition - the vegvísir and ægishjálmur
are 19th-century Icelandic magical staves, not Viking Age runework; the
popular "blue woad Pictish tattoo" image is weakly supported by real
evidence; Highland tartan/clan heraldry as commonly known today owes a lot
to 19th-century Victorian revival. Always say this plainly when relevant
rather than presenting later invention as ancient.

You are talking to members of the public through a free app, most of whom
you know nothing about. Be especially careful never to let an answer read
as more authoritative than it is.

Answer only from the real, sourced knowledge excerpts provided below, plus
your own general knowledge where it is clearly reliable - never invent
specific traditional details, names, or claims. Mark your own confidence
honestly, the same way the source research does. The excerpts below are
the most relevant sections retrieved for this specific question, not the
entire knowledge base - if they genuinely don't cover something the
question asked about, say so plainly rather than guessing; do not assume
silence in the excerpts means nothing is known anywhere.
""".strip()


def _load_knowledge() -> str:
    files = sorted(KNOWLEDGE_DIR.glob("**/*.md")) if KNOWLEDGE_DIR.is_dir() else []
    if not files:
        return ""
    sections = [
        f"# SOURCE FILE: {path.name}\n\n{path.read_text(encoding='utf-8')}"
        for path in files
    ]
    return "\n\n---\n\n".join(sections)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "have", "what", "when",
    "where", "which", "should", "would", "could", "about", "from",
    "their", "they", "them", "does", "did", "are", "was", "were", "will",
    "can", "know", "tell", "explain", "please", "real", "someone",
    "something", "having", "person", "there",
}


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip('"\'') for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip('"\'')
    return meta, text[match.end():]


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    matches = list(_HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    if not matches:
        return [("(whole file)", text)]
    if matches[0].start() > 0:
        intro = text[: matches[0].start()].strip()
        if intro:
            sections.append(("(intro)", intro))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((heading, content))
    return sections


def _read_sections_from_disk() -> list[dict]:
    # Recursive - the vault is organised into Foundations/, Norse-Specific/,
    # Celtic-Specific/, and Clan-Specific/ subfolders.
    files = sorted(KNOWLEDGE_DIR.glob("**/*.md")) if KNOWLEDGE_DIR.is_dir() else []
    result = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        tradition_tags = [str(t).lower() for t in meta.get("tradition", [])]
        for heading, content in _split_into_sections(body):
            result.append(
                {"file": path.name, "heading": heading, "content": content, "tradition_tags": tradition_tags}
            )
    return result


def _question_terms(question: str) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(question)]
    return [w for w in words if w not in _STOPWORDS]


_BOILERPLATE_HEADINGS = {"(intro)"}


def _retrieve_relevant_own(question: str, char_budget: int = 9000, min_sections: int = 3) -> str:
    """Same real fix already proven in the Tohunga's Apprentice Public App:
    score every section by keyword overlap (down-weighting terms common
    across most sections, since they can't discriminate), plus a flat
    boost when a question's terms match a section's own frontmatter
    tradition: tag (ground truth, not inferred from prose)."""
    sections = [s for s in _all_sections() if s["heading"].strip().lower() not in _BOILERPLATE_HEADINGS]
    if not sections:
        return ""
    terms = _question_terms(question)

    total = len(sections)
    doc_freq = {
        term: sum(1 for s in sections if term in s["content"].lower() or term in s["heading"].lower())
        for term in terms
    }

    scored = []
    for sec in sections:
        heading_l = sec["heading"].lower()
        content_l = sec["content"].lower()
        score = 0.0
        matched_terms = 0
        for term in terms:
            freq = doc_freq.get(term, 0)
            if freq == 0 or freq / total > 0.5:
                continue
            weight = 1.0 / freq
            local = 0.0
            if term in heading_l:
                local += 15 * weight
            occurrences = content_l.count(term)
            if occurrences:
                local += min(occurrences, 5) * 4 * weight
                matched_terms += 1
            score += local
        if any(any(term in tag for tag in sec["tradition_tags"]) for term in terms):
            score += 40
        if matched_terms >= 2:
            score *= 1.5
        scored.append((score, sec))
    scored.sort(key=lambda item: -item[0])

    selected: list[str] = []
    used = 0
    for score, sec in scored:
        if score <= 0 or used >= char_budget:
            break
        block = f"[{sec['file']} — {sec['heading']}]\n{sec['content']}"
        selected.append(block)
        used += len(block)

    if len(selected) < min_sections:
        for score, sec in scored:
            if len(selected) >= min_sections or used >= char_budget:
                break
            block = f"[{sec['file']} — {sec['heading']}]\n{sec['content']}"
            if block in selected:
                continue
            selected.append(block)
            used += len(block)

    return "\n\n---\n\n".join(selected)


# Knowledge sections are held in memory and only ever swapped for a
# complete, non-empty set. Retrieval used to read the knowledge folder from
# disk on every single request, which raced with the refresh thread's
# rebuild of that same folder - see sync_knowledge.sync(). A half-written
# folder can no longer reach a real question.
_SECTIONS_LOCK = threading.Lock()
_SECTIONS: list[dict] = []


# The rest of the whanau's knowledge - every other apprentice's vault - via
# the Koro Global Hub's warm cache (Koro, 2026-09-09: "I want it"). Local
# only; if the Hub is not running this adds nothing and the app answers from
# its own vault exactly as before.
WHANAU_KNOWLEDGE_URL = "http://127.0.0.1:8765/api/v1/whanau-knowledge"


def _whanau_knowledge(question: str) -> str:
    try:
        import json as _json
        import urllib.parse as _up
        import urllib.request as _ur

        own_vault = str(getattr(sync_knowledge, "SOURCE", "") or "")
        url = WHANAU_KNOWLEDGE_URL + "?" + _up.urlencode(
            {"q": question[:600], "exclude": own_vault, "chars": 3500, "sections": 4}
        )
        with _ur.urlopen(url, timeout=8) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        return str(data.get("knowledge", "")).strip()
    except Exception:
        return ""


def _retrieve_relevant(question: str, char_budget: int = 9000, min_sections: int = 3) -> str:
    """This app's own knowledge first (the original body, untouched, as
    _retrieve_relevant_own), then the relevant sections from the other
    apprentices' vaults, each labelled with the apprentice it came from."""
    own = _retrieve_relevant_own(question, char_budget=char_budget, min_sections=min_sections)
    wider = _whanau_knowledge(question)
    if not wider:
        return own
    if not own:
        return wider
    return own + "\n\n---\n\n" + wider


def _rebuild_sections() -> int:
    global _SECTIONS
    try:
        fresh = _read_sections_from_disk()
    except OSError:
        return len(_SECTIONS)  # keep the last good set rather than going blank
    if fresh:
        with _SECTIONS_LOCK:
            _SECTIONS = fresh
    return len(fresh)


def _all_sections() -> list[dict]:
    with _SECTIONS_LOCK:
        return _SECTIONS


KNOWLEDGE = _load_knowledge()
_rebuild_sections()
_last_refresh: dict = {"at": None, "synced_files": 0, "dropped_paragraphs": 0, "error": None}

REFRESH_INTERVAL_HOURS = float(os.environ.get("SEERS_APPRENTICE_REFRESH_HOURS", "24"))


def _refresh_loop() -> None:
    global KNOWLEDGE
    while True:
        try:
            if sync_knowledge.SOURCE.is_dir():
                result = sync_knowledge.sync()
                KNOWLEDGE = _load_knowledge()
                _rebuild_sections()
                _last_refresh.update(
                    at=datetime.now(timezone.utc).isoformat(),
                    synced_files=result["synced_files"],
                    dropped_paragraphs=result["dropped_paragraphs"],
                    error=None,
                )
            else:
                _last_refresh.update(
                    at=datetime.now(timezone.utc).isoformat(),
                    error=f"Private vault not reachable from this process: {sync_knowledge.SOURCE}",
                )
        except Exception as exc:  # noqa: BLE001 - a failed refresh should never crash the server
            _last_refresh.update(at=datetime.now(timezone.utc).isoformat(), error=str(exc))
        time.sleep(max(300, REFRESH_INTERVAL_HOURS * 3600))


threading.Thread(target=_refresh_loop, daemon=True).start()

WEB_DIST_DIR = BASE_DIR.parent / "app" / "dist"
_web_app_built = WEB_DIST_DIR.is_dir() and (WEB_DIST_DIR / "index.html").is_file()

app = Flask(
    __name__,
    static_folder=str(WEB_DIST_DIR) if _web_app_built else None,
    static_url_path="",
)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    window_start = now - 86400
    recent = [t for t in _request_log[ip] if t > window_start]
    _request_log[ip] = recent
    if len(recent) >= MAX_REQUESTS_PER_DAY_PER_IP:
        return True
    _request_log[ip].append(now)
    return False



def _authenticated_user_id() -> int | None:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    return patient_store.resolve_session(token) if token else None


CONSENT_TEXT = (
    "Creating an account lets me remember our real conversation history so "
    "you don't have to re-explain yourself every time - your messages are "
    "stored encrypted on Koro's own server. You can delete your account and "
    "every stored message permanently at any time. This is optional - you "
    "can keep using me anonymously with no account and nothing stored."
)


@app.post("/auth/signup")
def auth_signup():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))
    consent = bool(payload.get("consent", False))
    try:
        user_id = patient_store.create_user(email, password, consent)
    except patient_store.AccountError as exc:
        return jsonify({"error": str(exc)}), 400
    token = patient_store.create_session(user_id)
    return jsonify({"token": token, "email": email})


@app.post("/auth/login")
def auth_login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))
    try:
        user_id = patient_store.authenticate_user(email, password)
    except patient_store.AccountError as exc:
        return jsonify({"error": str(exc)}), 401
    token = patient_store.create_session(user_id)
    return jsonify({"token": token, "email": email})


@app.post("/auth/logout")
def auth_logout():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    if token:
        patient_store.destroy_session(token)
    return jsonify({"ok": True})


@app.get("/auth/me")
def auth_me():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"authenticated": False, "consent_text": CONSENT_TEXT})
    return jsonify({"authenticated": True})


@app.get("/conversations/history")
def conversation_history():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in."}), 401
    history = patient_store.get_recent_history(user_id)
    return jsonify({"messages": [{"role": m["role"], "text": m["content"]} for m in history]})


@app.post("/account/delete")
def account_delete():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Not logged in."}), 401
    patient_store.delete_user(user_id)
    return jsonify({"ok": True})


@app.get("/")
def index():
    if _web_app_built:
        return app.send_static_file("index.html")
    return jsonify(
        {
            "name": APP_NAME,
            "status": "ok" if OPENAI_API_KEY else "not configured (missing OPENAI_API_KEY)",
            "web_app_built": _web_app_built,
            "knowledge_files_loaded": len(list(KNOWLEDGE_DIR.glob("**/*.md"))) if KNOWLEDGE_DIR.is_dir() else 0,
            "disclaimer": DISCLAIMER,
        }
    )


@app.get("/api/status")
def status():
    return jsonify(
        {
            "name": APP_NAME,
            "status": "ok" if OPENAI_API_KEY else "not configured (missing OPENAI_API_KEY)",
            "web_app_built": _web_app_built,
            "knowledge_files_loaded": len(list(KNOWLEDGE_DIR.glob("**/*.md"))) if KNOWLEDGE_DIR.is_dir() else 0,
            "last_verified_refresh": _last_refresh,
            "disclaimer": DISCLAIMER,
        }
    )


@app.post("/ask")
def ask():
    if not OPENAI_API_KEY:
        return jsonify({"error": "Server not configured - no OPENAI_API_KEY set."}), 500

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if _rate_limited(ip):
        return jsonify(
            {"error": f"Daily question limit reached ({MAX_REQUESTS_PER_DAY_PER_IP}/day). Try again tomorrow."}
        ), 429

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    device_id = str(payload.get("device_id", "")).strip()
    if not question:
        return jsonify({"error": "A question is required."}), 400
    if not KNOWLEDGE:
        return jsonify({"error": "Knowledge base is empty - run sync_knowledge.py first."}), 500

    user_id = _authenticated_user_id()

    history_block = ""
    memory_ctx = None
    if user_id:
        # Real account (see patient_store.py) - use its own richer history.
        history = patient_store.get_recent_history(user_id)
        if history:
            lines = [f"{h['role'].upper()}: {h['content']}" for h in history]
            history_block = (
                "Real prior conversation history with this same person (for continuity only):\n\n"
                + "\n\n".join(lines)
                + "\n\n---\n\n"
            )
    elif device_id:
        # No account - most visitors never sign up. Real, permanent,
        # anonymous device-based memory instead (device_memory.py), per
        # Koro's own confirmed design: no login required to be remembered.
        memory_ctx = device_memory.build_memory_context(device_id, question)
        history_block = memory_ctx["prompt_section"]

    relevant = _retrieve_relevant(question)
    if not relevant.strip():
        # Never call the model with an empty knowledge block. With nothing
        # retrieved it answers from its own recall - invented facts, figures
        # and requirements - to a real person who will act on them.
        return jsonify(
            {
                "answer": (
                    "I'm sorry - I don't have anything in my knowledge here that "
                    "actually answers that, and I won't guess at it, because you'd "
                    "be acting on a guess.\n\n"
                    "Try asking it again in different words and I'll look again."
                ),
                "disclaimer": DISCLAIMER,
            }
        )

    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"{history_block}Relevant knowledge excerpts:\n\n{relevant}\n\n---\n\nQuestion: {question}"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        answer = response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to get an answer: {exc}"}), 502

    if user_id:
        patient_store.save_message(user_id, "user", question)
        patient_store.save_message(user_id, "assistant", answer)
    elif memory_ctx and memory_ctx["active"]:
        device_memory.remember_exchange(device_id, memory_ctx["person_name"], question, answer)

    return jsonify({"answer": answer, "disclaimer": DISCLAIMER})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8421"))
    app.run(host="0.0.0.0", port=port)
