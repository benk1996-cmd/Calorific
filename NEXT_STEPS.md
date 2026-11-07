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

Verified so far:
- Backend: 155 pytest tests pass (94% coverage over `backend/` + `scripts/`; the calculator is at 100%).
- Frontend: `tsc`, `vite build` and 25 Vitest tests pass. The chart was rendered to an image and checked.
- Supabase: `0001` and `0002` applied; `food_reference` holds 13,224 USDA foods (SR Legacy + FNDDS), 21 MB of 500 MB.
- Locally: login, onboarding and typed logging with Undo worked in mock mode.

**Not verified yet (needs your accounts):** everything on Vercel, any real OpenRouter call, photo upload from a phone camera, and the full UI after M4/M5 (I could not drive a browser; only the logic and the rendered chart were checked).

## Pending — needs you

1. **Smoke-test M4/M5 locally** (mock mode): Today screen (ring, bars, edit/swap/delete, manual add), History tab (7/30 days, table view, CSV). Report anything odd with the exact message.
2. **Deploy to Vercel** (first time): import the repo, add env vars (keep `LLM_MOCK=true`), open `/api/health`, add the Vercel URL to Supabase redirect URLs. *Heads-up:* I moved the backend from `api/` to `backend/` and added `includeFiles` in `vercel.json` so the Python function can import it. This is the least-tested part; if `/api/health` fails, send me the build log.
3. **Real model test:** set `OPENROUTER_API_KEY`, allow free endpoints in OpenRouter privacy settings, set `LLM_MOCK=false`, and log a few meals. Each analysis uses 1–3 of the 50 daily calls. Tell me what the real output looks like; the prompts probably need tuning.
4. **Eval:** put 30–50 photos in `eval/images/` and create `eval/labels.csv` (`filename,expected_dish,expected_kcal`). Run `python -m scripts.eval --dry-run` first. A full run (images × 4 models) exceeds the free daily quota, so use `--limit` and `--models`, spread over days. Then reorder `VISION_MODELS` by the results.
5. **SG FoodID (HPB) data:** no API or bulk download found. Options: the tool's download button for the dishes you eat, ask HPB, or hand-type a CSV. Until then SG dishes use USDA or flagged model estimates. Then `python -m scripts.ingest_sgfoodid` and send me the columns for the YAML map.
6. Optional: USDA Foundation Foods (re-extract the zip; the folder is missing `food.csv` and `food_nutrient.csv`), `USDA_API_KEY`, and commit `package-lock.json` if it isn't committed yet.

## Known caveats
- Trigram matching favours short names and USDA descriptions are long, so expect some misses. Tune `RESOLVER_THRESHOLD` once real data and eval results exist.
- `RESOLVER_LLM_PICK` is only a hook, not wired to a model (off by default, as specified).
- The History target line uses your current target for every past day.
- Food search does a sequential scan, which is fine at ~13k rows.
- Per-request rate limiting beyond the daily quota isn't implemented (serverless instances don't share memory). The daily caps are the guard.
- Free OpenRouter models change often; if a model ID disappears, edit `VISION_MODELS`.

## Next step to run

Start with item 1 above, then deploy (item 2). Local run reminder:

```bash
# terminal 1 (backend)
source .venv/bin/activate && set -a && source .env && set +a
python -m uvicorn backend.main:app --reload --port 8000
# terminal 2 (frontend)
npm run dev
```
