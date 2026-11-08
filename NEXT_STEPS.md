# Calorific — Status & Next Steps

_Last updated: 2026-11-08. Plan: [BUILD_PLAN.md](BUILD_PLAN.md). Setup and usage: [README.md](README.md)._

## Done — all milestones built

| Milestone | Status | Notes |
|---|---|---|
| M0 Scaffold | Built | Vite/React/TS/Tailwind PWA, FastAPI, Supabase migration `0001`, CI, `vercel.json` |
| M1 Auth & profile | Built, **working locally** | Magic-link login (invite-only), onboarding, Mifflin-St Jeor targets |
| M2 Data layer | Built, USDA data loaded | `0002_search.sql`, ingest scripts, USDA API client, resolver, food search |
| M3 Recognition | Built, **works in mock mode locally** | Calculator, OpenRouter client + fallbacks, quota guard, analyze endpoints, capture UI |
| M4 Dashboard & editing | Built | Calorie ring, macro/sugar/sodium bars, meal list, edit/swap/delete, manual add |
| M5 History & export | Built | 7/30-day chart with target line, averages, table view, CSV export |
| M6 Eval & hardening | Built | `scripts/eval.py`, friendly error states, upload limits, security headers, full README |
| UI/UX redesign | Built, screenshot-tested | Design tokens + dark mode, bottom nav with centre Add button, Add sheet, hero calorie ring, macro/limit bars, progress banner and Undo toast, portion steppers with auto-save, 3-step onboarding, friendlier login. See README "Design system" |

Verified so far:
- Backend: 155 pytest tests pass (94% coverage over `backend/` + `scripts/`; the calculator is at 100%).
- Frontend: `tsc`, `vite build` and 35 Vitest tests pass. The redesigned screens were rendered in headless Chromium (light and dark, 320–430px wide) and checked for overflow and tap-target size.
- Supabase: `0001` and `0002` applied; `food_reference` holds 13,224 USDA foods (SR Legacy + FNDDS), 21 MB of 500 MB.
- Locally: login, onboarding and typed logging with Undo worked in mock mode.

**Not verified yet (needs your accounts):** everything on Vercel, any real OpenRouter call, photo upload from a phone camera, and the full UI after M4/M5 (I could not drive a browser; only the logic and the rendered chart were checked).

## Blocker right now: login email rate limit

Supabase's built-in email sender allows only a few login emails per hour for the whole project, and it returned **"email rate limit exceeded"**. To get in: wait about an hour and request **one** link (check spam, and any session still open in another tab or browser still works). To fix it for good, set up **custom SMTP**:
1. Create a free account with an email sender such as Resend, verify a sender address or domain, and create an SMTP key.
2. Supabase → Project Settings → Authentication → SMTP Settings → enable custom SMTP and enter the host, port, user, password and sender address.
3. Authentication → Rate Limits → raise the email limit (editable only once custom SMTP is on).

You need a link only once per browser; the installed PWA and the regular browser keep separate sessions.

## Pending — needs you

1. **Smoke-test M4/M5 locally** (mock mode): Today screen (ring, bars, edit/swap/delete, manual add), History tab (7/30 days, table view, CSV). Report anything odd with the exact message.
2. **Deploy to Vercel** (first time): import the repo, add env vars (keep `LLM_MOCK=true`), open `/api/health`, add the Vercel URL to Supabase redirect URLs. *Heads-up:* I moved the backend from `api/` to `backend/` and added `includeFiles` in `vercel.json` so the Python function can import it. This is the least-tested part; if `/api/health` fails, send me the build log.
3. **Real model test:** typed logging is **verified against the real OpenRouter** (key valid, free tier, ~2–3 s, correct items and modifiers). Still to check: a real **photo** analysis (I haven't sent a food photo). Each analysis uses 1–3 of the 50 daily calls. Gemma is often "temporarily rate-limited upstream"; the fallback handles it, but tell me if photos keep failing. To free the app's own counter after the earlier failed attempts, run `delete from usage_counters;` in the Supabase SQL Editor.
4. **Eval:** put 30–50 photos in `eval/images/` and create `eval/labels.csv` (copy [eval/labels.example.csv](eval/labels.example.csv)). Columns: `filename` (exact name in `eval/images/`), `expected_dish` (HPB-style name), `expected_kcal` (a number for the whole meal, from the closest SG FoodID entry). Quote dish names that contain commas. Use JPEG or PNG (convert iPhone HEIC first) and include a few tricky photos and one non-food photo. Run `python -m scripts.eval --dry-run` first. A full run (images × 4 models) exceeds the free daily quota, so use `--limit` and `--models`, spread over days. Then reorder `VISION_MODELS` by the results. `labels.csv` is not gitignored; keep it out of a public repo if its calories come from HPB.
5. **SG FoodID (HPB) data:** no API or bulk download found. Options: the tool's download button for the dishes you eat, ask HPB, or hand-type a CSV. Until then SG dishes use USDA or flagged model estimates. Then `python -m scripts.ingest_sgfoodid` and send me the columns for the YAML map.
6. **Env settings:** leave `TEXT_MODELS=` blank (it falls back to `VISION_MODELS`). Set `USDA_API_KEY` from https://fdc.nal.usda.gov/api-key-signup (optional; enables the live USDA fallback) and restart the backend. Add both to Vercel too.
7. **Optional text model:** if Gemma parses typed meals badly or is often busy, put a plain chat (non-reasoning) free model first in `TEXT_MODELS` and keep Gemma as the fallback. Check openrouter.ai/models for current free IDs; reasoning models can use up the 1,500-token output limit and return empty JSON. I can add a text mode to the eval script if you want to compare them.
8. Optional: USDA Foundation Foods (re-extract the zip; the folder is missing `food.csv` and `food_nutrient.csv`), and commit `package-lock.json` if it isn't committed yet.

## Known caveats
- OpenRouter allows at most 3 models per request; the app splits `VISION_MODELS` into groups of 3. A fallback attempt counts toward the daily quota, and failed attempts are counted too (a 400/401 from OpenRouter still used one of your 10 per-user calls before the fix).
- Trigram matching favours short names and USDA descriptions are long, so expect some misses. Tune `RESOLVER_THRESHOLD` once real data and eval results exist.
- `RESOLVER_LLM_PICK` is only a hook, not wired to a model (off by default, as specified).
- The History target line uses your current target for every past day.
- Food search does a sequential scan, which is fine at ~13k rows.
- Per-request rate limiting beyond the daily quota isn't implemented (serverless instances don't share memory). The daily caps are the guard.
- Free OpenRouter models change often; if a model ID disappears, edit `VISION_MODELS` (or `TEXT_MODELS`).
- `scripts/eval.py` tests photos only. There is no eval for typed-meal parsing yet.

## Next step to run

1. Get logged in again (wait out the email limit, then set up custom SMTP).
2. Smoke-test M4/M5 (item 1), then deploy (item 2). Local run reminder:

```bash
# terminal 1 (backend)
source .venv/bin/activate && set -a && source .env && set +a
python -m uvicorn backend.main:app --reload --port 8000
# terminal 2 (frontend)
npm run dev
```
