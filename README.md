# Calorific

A photo-based calorie tracker for Singapore food. Snap or upload a meal, or type it in. A free vision model on OpenRouter identifies the food and portion. Calories and nutrients come from Singapore HPB data first, then USDA, then the model's own estimate. The meal is logged automatically and your daily total is tracked against a target calculated from your profile.

Stack: React + Vite + TypeScript + Tailwind PWA · FastAPI (Vercel Python Functions) · Supabase (Postgres + magic-link auth) · OpenRouter free models. Design decisions are in [BUILD_PLAN.md](BUILD_PLAN.md); current status is in [NEXT_STEPS.md](NEXT_STEPS.md).

## How it works

```
photo / typed text → vision or text LLM (OpenRouter, free, one request per analysis)
   → items[] → resolver: SG FoodID exact/alias → SG trigram → local USDA trigram → live USDA API → model estimate
   → calculator (per-serving or per-100g × grams, modifiers like "less rice", "kosong")
   → meal saved automatically → daily summary (always a SUM over rows)
```

- **Fully automatic logging.** Every meal can be edited, re-portioned, food-swapped or deleted afterwards. A 10-second Undo shows after logging.
- **Estimates are flagged** with ⚠ (no database match, or model confidence below 0.5).
- **Photos are never stored.** They are resized in the browser (≤1280px JPEG, EXIF stripped), sent to the model, and discarded. The server checks the real file type and size (≤1.5 MB), keeps uploads in memory, and never logs image bytes.
- **Invite-only.** Sign-up is disabled; you add people in Supabase.
- **Free-tier quota guard.** Every model request counts toward a per-user cap (default 10/day) and a global cap (default 45/day), reset at midnight Singapore time. At the cap you get "Daily AI limit reached. Use search to add food manually." Manual search-and-add never calls a model.

## Project layout

```
api/index.py        Vercel entrypoint (thin; imports backend.main)
backend/            FastAPI app: routers_*.py, services/ (calc, resolver, usda, llm, analyzer, tally, ...)
src/                React app (pages/, components, lib/)
supabase/migrations SQL schema, RLS policies, search functions
scripts/            ingest_sgfoodid.py, ingest_usda.py, eval.py
tests/              pytest (backend + scripts); src/**/*.test.ts for Vitest
data/raw/           datasets (gitignored)      eval/images/  eval photos (gitignored)
```

The backend lives in `backend/`, not `api/`, because Vercel deploys every Python file inside `api/` as its own function.

## Setup

### 1. Supabase (database and login)
1. Create a project at supabase.com. Pick the **Singapore** region and save the database password.
2. **SQL Editor** → run `supabase/migrations/0001_init.sql`, then `0002_search.sql` (each as one script).
3. **Authentication → Sign In / Providers**: keep Email on and switch **off** "Allow new users to sign up".
4. **Authentication → URL Configuration**: add `http://localhost:5173/**` and, after your first deploy, `https://<your-app>.vercel.app/**` to *Redirect URLs*. Set *Site URL* to your Vercel URL once you have one.
5. **Authentication → Users → Add user → Invite user** for yourself and each friend or family member. Only invited emails can sign in. You can also set `ALLOWED_EMAILS` as a second check.
6. **Project Settings → API**: copy the project URL, the anon (publishable) key and the service-role (secret) key. The service-role key is server-side only and must never go in a `VITE_` variable.

Supabase's built-in email sender is rate-limited (a few emails an hour). For more than a handful of users, set up custom SMTP.

### 2. OpenRouter (free vision models)
1. Create a key at openrouter.ai → Keys.
2. **Settings → Privacy**: allow free endpoints that may log or train on prompts. Without this most free models are not offered. This is accepted for the proof of concept.
3. The free tier allows **50 requests/day for the whole account** and 20/minute. Each analysis uses 1 request, up to 3 when retrying. Models in `VISION_MODELS` are tried through OpenRouter's fallback list. The free catalogue changes often, so run the eval (below) and edit the list when a model disappears.

### 3. USDA API key (optional but recommended)
Get a free key at https://fdc.nal.usda.gov/api-key-signup. It powers the last-resort live lookup (1,000 requests/hour); results are cached in your database.

### 4. Environment variables
Copy `.env.example` to `.env` for local use, and add the same values in Vercel → Project → Settings → Environment Variables.

| Variable | Purpose |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Backend database and auth |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | Frontend (baked in at build time; anon key only) |
| `OPENROUTER_API_KEY`, `VISION_MODELS`, `TEXT_MODELS` | Models (`TEXT_MODELS` defaults to `VISION_MODELS`) |
| `LLM_MOCK` | `true` (default) uses a fake model so the quota is never spent. Set `false` for real calls |
| `USDA_API_KEY` | Live USDA fallback |
| `ALLOWED_EMAILS` | Optional comma-separated allow-list |
| `ANALYZE_DAILY_LIMIT_GLOBAL` / `_PER_USER` | Quota caps (45 / 10) |
| `RESOLVER_THRESHOLD` | Fuzzy match cut-off (0.45). `RESOLVER_LLM_PICK` stays `false` |
| `RICE_KCAL_SHARE`, `LESS_RICE_FACTOR`, `NO_SUGAR_REMOVAL`, `SIEW_DAI_REMOVAL` | Optional calculator tuning |
| `APP_URL` | Sent to OpenRouter as the referer |

## Food data

Raw datasets live in `data/raw/` (gitignored; never commit HPB data):

```
data/raw/sgfoodid/                   SG FoodID exports (CSV/XLSX, any number of files)
data/raw/usda/foundation|sr_legacy|fndds/   unzipped USDA CSVs (food.csv, food_nutrient.csv, ...)
```

Install the script dependencies once: `pip install -r requirements-scripts.txt`. Scripts read `.env` themselves.

**USDA** (Foundation, SR Legacy, optionally FNDDS; missing folders are skipped):
```bash
python -m scripts.ingest_usda --dry-run   # parse only
python -m scripts.ingest_usda             # upload; prints row counts and database size (free limit 500 MB)
```

**SG FoodID (HPB).** HPB offers no API or confirmed bulk download; check the tool's download option and its [terms of use](https://file.go.gov.sg/termsofuse-hpbsgfoodid.pdf). The app works without it; Singapore dishes then resolve through USDA or the model's flagged estimate.
```bash
python -m scripts.ingest_sgfoodid        # prints columns + samples, then STOPS
cp scripts/sgfoodid_map.example.yaml scripts/sgfoodid_map.yaml   # map your column names
python -m scripts.ingest_sgfoodid --map scripts/sgfoodid_map.yaml --dry-run
python -m scripts.ingest_sgfoodid --map scripts/sgfoodid_map.yaml
```
Both scripts are idempotent: re-running updates existing rows.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
npm install

# terminal 1: backend
set -a && source .env && set +a
python -m uvicorn backend.main:app --reload --port 8000
# terminal 2: frontend (proxies /api to :8000)
npm run dev                                  # http://localhost:5173
```
Check the API at http://localhost:8000/api/health. Alternatively `vercel dev` (Vercel CLI, after `vercel link`) runs the frontend and the Python function together the way production does.

Keep `LLM_MOCK=true` while developing. The mock always returns "Chicken rice" for photos and splits typed text on `+`, `,`, `&` and "and".

### Tests
```bash
pytest                                  # backend + scripts (uses fakes; no network, no keys)
pytest --cov=backend --cov-report=term-missing
npm test                                # frontend logic (Vitest)
npm run build                           # type-check + production build
```
Tests mock OpenRouter, Supabase and USDA. They cover targets, the calculator (100% coverage), the resolver on ~20 Singapore dishes, the midnight-SGT day boundary, quota caps, editing, history/CSV, and that one user can never read or change another user's data.

## Evaluating models

Put 30–50 photos of meals you eat in `eval/images/` and a `eval/labels.csv` with `filename,expected_dish,expected_kcal` (take the last two from the closest SG FoodID entry). Then:

```bash
python -m scripts.eval --dry-run                  # shows images × models = calls
python -m scripts.eval --limit 10 --models google/gemma-4-31b-it:free
python -m scripts.eval --mock --no-resolver       # pipeline smoke test (no key, no quota)
```
It runs each model on each photo (one raw request, no retries) and reports **recognition accuracy, resolver accuracy, mean absolute kcal error, latency and failure rate**, saving `eval/results/eval_*.md|csv`. Use the result to order `VISION_MODELS`, best first.

**Mind the quota.** Calls = images × models, and the free tier allows 50 a day for the whole app. The script refuses more than 45 planned calls unless you pass `--yes`. Spread a full run over several days with `--limit`/`--models`, and note that eval calls also eat the quota your users need that day.

## Deploying (Vercel)

1. Push the repo to GitHub and **Import** it at vercel.com. The framework is detected as Vite; `vercel.json` sets the output directory, routes `/api/*` to the Python function (`api/index.py`, 300 s limit), serves the SPA for other paths and adds security headers.
2. Add all environment variables before the first deploy (keep `LLM_MOCK=true` until you have tested). `VITE_*` changes need a redeploy.
3. Open `https://<app>.vercel.app/api/health`. Expect `"status":"ok"`.
4. Add the Vercel URL to Supabase *Site URL* and *Redirect URLs*.
5. Pushes to `main` deploy to production; pull requests get preview deploys (add preview URLs to Supabase redirect URLs if you want to log in on them).

The Vercel Hobby plan is for non-commercial use, which suits friends and family.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Internal Server Error" on the first screen | Backend not running (start it, see Local development) |
| "Signups not allowed for otp" | The email isn't in Supabase → Authentication → Users |
| Magic link opens localhost or "redirect not allowed" | Missing entry in Supabase Redirect URLs |
| 401 / "session expired" | Wrong `SUPABASE_URL`/anon key in the backend, or the session expired (sign in again) |
| 409 "Complete your profile first" | Finish onboarding |
| 429 "Daily AI limit reached" | Per-user or global cap hit; use search to add food, or wait for midnight SGT |
| 503 "AI service is busy" | All fallback models failed or rate-limited; try again shortly |
| Everything is ⚠ and 300 kcal | `LLM_MOCK=true`, or no database match (load more food data) |
| `function ... does not exist` | A migration hasn't been run |

## Privacy and limits
- Photos are processed in memory and never stored; logs never contain image data or request bodies.
- Free OpenRouter endpoints may log prompts and images. That is allowed for this proof of concept; do not upload anything sensitive.
- Row Level Security is enabled on all user tables, and every backend query is also scoped to the signed-in user.
- Only meal and nutrient data, your profile and daily AI-call counts are stored.
