# Calorific

Photo-based calorie tracker (React/Vite PWA + FastAPI on Vercel + Supabase). See [BUILD_PLAN.md](BUILD_PLAN.md).

## Local dev (M0)
```bash
cp .env.example .env
pip install -r requirements-dev.txt && pytest
python -m uvicorn backend.main:app --reload --port 8000   # backend
npm install && npm run dev                    # frontend (proxies /api to :8000)
```
Full setup docs (Supabase, keys, ingestion, eval) are completed in M6.

## M1: auth & profile
- Magic-link login with `shouldCreateUser: false`. Invite users in Supabase → Authentication → Users → Invite, and disable public sign-ups (Auth → Providers → Email → "Allow new users to sign up" off). Optionally set `ALLOWED_EMAILS`.
- The API validates each bearer token against `SUPABASE_URL/auth/v1/user`, then scopes all queries by `user_id`.
- In Supabase Auth → URL Configuration, add your Vercel URL and `http://localhost:5173` as redirect URLs.

## M2: data layer
1. Run `supabase/migrations/0002_search.sql` in the Supabase SQL editor (adds `search_foods` and `db_size_mb`).
2. Local script deps: `pip install -r requirements-scripts.txt`. Scripts read `.env` themselves.
3. **SG FoodID:** put exports in `data/raw/sgfoodid/`, then
   `python -m scripts.ingest_sgfoodid` — prints columns + samples and stops.
   Create `scripts/sgfoodid_map.yaml` from `scripts/sgfoodid_map.example.yaml`, then
   `python -m scripts.ingest_sgfoodid --map scripts/sgfoodid_map.yaml --dry-run` and again without `--dry-run`.
4. **USDA:** unzip into `data/raw/usda/{foundation,sr_legacy,fndds}/`, then `python -m scripts.ingest_usda`
   (use `--dry-run` first; prints row counts and DB size, free limit 500 MB).
5. Resolver order: SG exact/alias → SG trigram → local USDA trigram → live USDA API (needs `USDA_API_KEY`) → model estimate.
   Tune with `RESOLVER_THRESHOLD`. `GET /api/foods/search?q=` powers manual search.

## M3: recognition
- `POST /api/analyze/photo` (multipart `image`, optional `note`) and `POST /api/analyze/text` (`{text}`) call the LLM, resolve foods, calculate nutrients and **auto-save the meal**. `GET /api/usage` shows remaining AI logs; `DELETE /api/meals/{id}` powers Undo.
- **Mock mode is the default** (`LLM_MOCK=true`): a deterministic fake replaces OpenRouter so the 50/day free quota is never spent. Set `LLM_MOCK=false` and `OPENROUTER_API_KEY` for real calls.
- Every model request (including retries) counts toward `ANALYZE_DAILY_LIMIT_PER_USER` / `ANALYZE_DAILY_LIMIT_GLOBAL`, reset at midnight SGT. At most 3 requests per analysis.
- Photos are read into memory, validated by magic bytes (JPEG/PNG/WebP, ≤1.5 MB), sent to the model and discarded.

## M4: Today dashboard & editing
- `GET /api/days/{date}/summary` returns meals with items plus totals, targets, remaining, by-meal and item count (always a SUM over rows). The Today screen shows the calorie ring, macro bars and sugar/sodium caps (red when over).
- Edit: `PATCH /api/meals/{id}` (meal type, note), `PATCH /api/meal-items/{id}` (swap food, grams, servings, name), `DELETE` for meals and items, `POST /api/meals/{id}/items` to add food to a meal.
- `POST /api/meals/manual` logs a food from search with **no model call**, so it works after the daily AI cap. Edited items are marked `user_edited`.
- With no reference food (estimates), changing the portion scales the existing nutrients proportionally.

## M5: History & export
- `GET /api/history?from=&to=` (max 90 days; defaults to the last 7 days in your timezone) returns a row per day (zero-filled), the per-day macros, averages over *logged* days and your current targets.
- `GET /api/export.csv?from=&to=` (max 366 days) downloads one row per food item. Text cells starting with `=`, `+`, `-` or `@` are prefixed with `'` so spreadsheets don't run them as formulas.
- The History tab shows 7/30-day calorie bars with a target line, daily averages, a table view and the CSV button. The target line uses your *current* target for every day (past targets aren't stored).
