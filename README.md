# United Kingdom - The Seer's Apprentice - Public App

Free, public knowledge-consultation app for Norse and Celtic tradition -
companion to New Zealand - The Tohunga's Apprentice (Māori tradition). Standalone from
Koro Global Hub, same reasoning: the Hub holds private tasks/family
info/other workers that should never face the public internet.

Real source of knowledge: `Documents\Norse_Celtic_Apprentice_Vault\Knowledge\`
(Koro's own dedicated vault, separate from his personal Obsidian vault and
separate from this app - `backend/sync_knowledge.py` pulls a filtered
snapshot, never a live path into his machine).

## What's actually built and tested, 2026-08-28

- `backend/app.py` - real Flask API (`POST /ask`, `GET /api/status`), same
  knowledge base and honesty system prompt as the private Hub worker
  (`workers/norse_celtic_apprentice.py`). Reads `OPENAI_API_KEY` from
  environment (its own funded key, not shared with the Tohunga's
  Apprentice app - public traffic on two apps is unpredictable cost that
  shouldn't be silently pooled). Built-in blunt cost/abuse safeguard
  (`MAX_REQUESTS_PER_DAY_PER_IP`, default 40/day, in-memory).
- `backend/sync_knowledge.py` - pulls a deliberate, filtered snapshot from
  the private vault (drops "Gap - flagged" and "Lower confidence"
  paragraphs, same honesty-tier filter the Tohunga's Apprentice app uses).
  **Tested live**: synced 18 files, dropped 1 unverified paragraph.
- **Tested live**: backend boots, loads 18 knowledge files, `/api/status`
  reports correctly, refresh loop runs and logs honestly, `/ask` fails
  gracefully (not crashes) with no key configured.

## What's genuinely NOT done yet - real next steps, in order

1. A real, funded `OPENAI_API_KEY` for this app specifically.
2. A real hosting decision for the backend (same options already
   identified for the Tohunga's Apprentice app: Render/Railway/Fly.io) -
   worth a short conversation with Koro before committing to recurring
   cost.
3. A separate Cloudflare tunnel (own isolated config, same pattern as
   `tohungas-apprentice-config.yml` - never touch the shared/production
   tunnel configs).
4. ~~The Expo (React Native) web/mobile app itself~~ - **done, 2026-08-28**:
   `app/` is a real Expo SDK 57 project (same pinned versions as the
   Tohunga's Apprentice app), `App.js` is a full working chat UI with its
   own dark/night colour scheme and disclaimer banner. **Verified via a
   real `npx expo export --platform web` build - exit 0, bundled clean
   (197 modules), and verified served correctly by `backend/app.py` at
   `/` (200, real HTML, correct title) with the backend running locally.**
   Not yet linked to a real Expo account/project (no `eas init` run yet -
   deliberately held off until Koro decides on account/ownership, see #5).
5. A real Expo project link (own `eas init`, own project id in
   `app.json`'s `extra.eas` - deliberately left out of this scaffold
   rather than guessing) - only needed once an EAS cloud build (Android
   APK) is wanted. Can reuse Koro's existing Expo account (`iamkoroteao`)
   or use a separate one - his call.
6. Apple/Google developer accounts only needed if going past the free web
   + Android-APK path (same real cost/timeline tradeoffs already
   explained for the Tohunga's Apprentice app).

## Local dev

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python sync_knowledge.py
$env:PORT = "8421"
.venv\Scripts\python app.py
```
