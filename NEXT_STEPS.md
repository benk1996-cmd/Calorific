# Calorific — Status & Next Steps

_Last updated: 2026-11-07. Plan: [BUILD_PLAN.md](BUILD_PLAN.md)._

## Done

| Milestone | Status | Notes |
|---|---|---|
| M0 Scaffold | Built, committed | Vite/React/TS/Tailwind PWA, FastAPI in `api/`, Supabase migration `0001`, `.env.example`, CI, `vercel.json` |
| M1 Auth & profile | Built, committed, **working locally** | Magic-link login (invite-only), onboarding, `GET/PUT /api/profile`, Mifflin-St Jeor targets |
| M2 Data layer | Built, committed, USDA data loaded | `0002_search.sql`, ingest scripts, USDA API client, resolver, `GET /api/foods/search` |
| M3 Recognition | Built, committed (mock mode) | Calculator, vision/text parsing, OpenRouter client + fallbacks, quota guard, `POST /api/analyze/photo|text`, auto-save, Undo, capture UI |
| M4 Dashboard & editing | Built, committed | Day summary, calorie ring, macro/sugar/sodium bars, meal list, edit/swap/delete, manual add (no model call) |

Verified so far:
- Backend: 133 pytest tests pass (calc has 100% coverage; targets, profile, resolver on 20 SG dishes, ingest, search, analyze, quota, tally).
- Frontend: `tsc`, `vite build` and 14 Vitest tests pass (checked by me in M3).
- Supabase: schema (`0001`, `0002`) applied. `food_reference` holds **13,224 USDA foods** (7,793 SR Legacy + 5,431 FNDDS), DB size 21.1 MB of 500 MB.
- Login works locally with an invited email.

## Pending

**Needs you**
- [ ] **SG FoodID (HPB) data**: no API or bulk download found. Options: use the tool's download button for the dishes you eat, ask HPB, or type ~50–100 dishes into a CSV. Until then, SG dishes resolve via USDA or the model's estimate (flagged). Read the [HPB terms](https://file.go.gov.sg/termsofuse-hpbsgfoodid.pdf) first. Then `python -m scripts.ingest_sgfoodid` → send me the columns → I write the YAML map.
- [ ] **USDA Foundation Foods**: `data/raw/usda/foundation/` is missing `food.csv` and `food_nutrient.csv`. Re-extract the zip. Optional (adds a few hundred foods).
- [ ] Confirm `select * from search_foods('fried rice', null, 0.15, 5);` returns rows in the Supabase SQL Editor (run it on its own).
- [ ] **Vercel**: first deploy not done. Import the repo, add all env vars (keep `LLM_MOCK=true`), check `/api/health`, then add the Vercel URL to Supabase Site URL and Redirect URLs.
- [ ] `USDA_API_KEY` (https://fdc.nal.usda.gov/api-key-signup) for the live USDA fallback.
- [ ] `OPENROUTER_API_KEY` + allow free endpoints that may log prompts (Settings → Privacy). Needed only for real calls; not for mock-mode M3 development.
- [ ] Commit `package-lock.json` (`git add package-lock.json && git commit`).
- [ ] Eval photos (30–50) in `eval/images/` and `eval/labels.csv`, needed for M6.

**Needs me (remaining milestones)**
- [ ] **M5** History: 7/30-day charts, averages, CSV export.
- [ ] **M6** Eval script, rate-limit and error states, full README.

## Known caveats
- Python function deploy on Vercel is untested (no `vercel dev` here). If `/api/health` 404s after deploying, send me the build log.
- Trigram matching favours short names, and USDA descriptions are long. Expect some misses, so tune `RESOLVER_THRESHOLD` once real data is in.
- The `RESOLVER_LLM_PICK` option is only a hook, not wired to a model.
- Search runs a sequential scan, not the trigram index. Fine at ~13k rows.
- `ingest_usda` was changed to accept FNDDS nutrient codes (208, 203…). Foundation hasn't been tested on real data.

## Next step to run

**Try M4 locally** (mock mode is fine): the Today screen should show a ring and bars. Log a meal by typing, tap *Edit*, change grams, *Swap food* (search "rice"), *Add food*, *Remove*, and *Delete meal*. Use *Search & add food manually* and confirm "AI logs left" does not change. Then say **"continue"** for M5 (History: 7/30-day charts, averages, CSV export).

Local run reminder:
```bash
# terminal 1 (backend)
source .venv/bin/activate && set -a && source .env && set +a
python -m uvicorn api.index:app --reload --port 8000
# terminal 2 (frontend)
npm run dev
```
