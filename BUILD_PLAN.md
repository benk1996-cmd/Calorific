# Calorific — Build Plan & Coding-Agent Prompt (v3, all decisions final)

A photo-based calorie tracker. You snap or upload a meal, or type it in. A free vision model on OpenRouter identifies the food and estimates the portion. Calories and nutrients come from Singapore HPB data first, then USDA. The meal is logged automatically and the daily total is updated against a target calculated for each user.

Parts:
1. Decisions (final)
2. Build plan, component by component
3. Data & keys to get before building — what, where from, where to put it
4. Coding-agent prompt (paste into Claude Code in your new repo)

---

## Part 1 — Decisions (final)

| ID | Decision | Choice |
|---|---|---|
| D1 | Platform | Mobile-first web app (PWA), hosted on **Vercel** |
| D2 | Backend | **Python** (FastAPI as Vercel Python Functions) |
| D3 | Recognition | **General multimodal LLM** with JSON output |
| D4 | Model provider | **OpenRouter free models** (see 2.3) with a fallback chain |
| D5 | Nutrition sources | **SG FoodID (HPB) → USDA FoodData Central → model estimate** |
| D6 | Portions | **Fully automatic logging.** User can still edit or delete a meal afterwards |
| D7 | Nutrients | **All:** kcal, protein, carbs, fat, sugar, sodium, fibre |
| D8 | Daily target | **Calculated** from age, sex, height, weight, activity level and goal (Mifflin-St Jeor × activity factor ± goal adjustment) |
| D9 | Users | **You + friends and family.** Invite-only accounts |
| D10 | Photos | **Deleted after analysis.** Processed in memory, never written to storage |
| D11 | Hosting | **Vercel** |
| D12 | Fallback input | **Typed description → NLP parse → same pipeline.** No barcode |
| D13 | Day boundary | **Midnight**, in the user's timezone (default Asia/Singapore) |
| D14 | History | **All:** 7- and 30-day charts, averages, CSV export |
| D15 | Build tooling | **Claude Code in a separate repo that you create yourself** (the agent does not run `git init` or create remotes) |
| D16 | Database & auth | **Supabase** (Postgres + magic-link auth) |
| D17 | OpenRouter tier | **Free only (proof of concept).** 50 model calls/day for the whole app; no $10 top-up |
| D18 | Provider data logging | **Allowed.** No restriction on free providers that log prompts |

### What Vercel hosting forces (decided for you; change if you disagree)
- **No SQLite.** Vercel functions have no persistent disk, so the database must be hosted. → **Supabase** (free tier): hosted Postgres **plus** built-in auth for invite-only accounts. The `pg_trgm` extension handles fuzzy food-name matching in the database.
- **Request body limit of 4.5 MB** per function call. Client-side resizing (≤1280px, ~300 KB) keeps uploads well under this.
- **Function time limit of 300s** on the Hobby plan. Plenty for one vision call plus one lookup, but the model call needs a timeout and a retry on the next fallback model.
- The Vercel **Hobby plan is for non-commercial use**. That's fine for friends and family. Charging money later means moving to Pro.

---

## Part 2 — Build plan

### 2.1 Pipeline

```
[Camera / upload]           [Typed text: "2 roti prata + teh tarik"]
      │ resize ≤1280px, JPEG, strip EXIF          │
      ▼                                           ▼
POST /api/analyze/photo                    POST /api/analyze/text
      │  vision LLM (OpenRouter free, fallback chain)  │  text LLM parse
      └──────────────► items[] (same JSON schema) ◄────┘
                              │
                              ▼
                 Nutrition resolver (Postgres)
          1. SG FoodID exact/alias  2. pg_trgm fuzzy
          3. LLM picks from top-5   4. USDA API (cached)
          5. Model estimate, flagged "estimated"
                              │
                              ▼
                 Calculator → nutrients per item
                              │
                              ▼
                 Auto-save meal  →  photo bytes discarded
                              │
                              ▼
          Daily summary (SUM over rows) vs personal target
                              │
                              ▼
         Result card: "Logged 620 kcal · Edit · Undo"
```

### 2.2 Components

**C1. Capture & input (frontend)**
- Home screen with three actions: *Take photo*, *Upload*, *Type it*.
- Camera via `<input type="file" accept="image/*" capture="environment">`. Vercel serves over HTTPS, so phone cameras work.
- Resize and compress in the browser, strip EXIF/GPS, and enforce ≤1 MB before upload.
- *Type it* is a free-text box with examples ("1 plate chicken rice less rice, kopi siew dai").
- After logging, show a result card with items, kcal, and **Edit** / **Undo** buttons (Undo stays available for 10 seconds, Edit at any time).

**C2. API (FastAPI on Vercel)**
- `POST /api/analyze/photo` — image (+ optional note) → resolve → **auto-save** → returns saved meal + updated daily summary
- `POST /api/analyze/text` — text → same flow
- `PATCH /api/meals/{id}`, `DELETE /api/meals/{id}`, `PATCH /api/meal-items/{id}` (swap food, change portion)
- `GET /api/days/{date}/summary`
- `GET /api/history?from=&to=` and `GET /api/export.csv?from=&to=`
- `GET /api/foods/search?q=` (used when editing)
- `GET/PUT /api/profile` (body stats, activity, goal → target recalculated)
- Every endpoint checks the Supabase session JWT. Every query is scoped to `user_id`, and Supabase Row Level Security is on as a second guard.

**C3. Food recognition (vision LLM via OpenRouter)**
- OpenAI-compatible client pointed at `https://openrouter.ai/api/v1`.
- Uses OpenRouter's `models` array so a single request falls through the fallback chain automatically when a model is rate-limited or down.
- Prompt context: the user is in Singapore. List every food and drink. Prefer HPB-style dish names. Treat a standard hawker plate or bowl as **one composite dish**. Estimate grams using the plate, bowl or utensils for scale. Note drink sugar level (kosong / siew dai / regular). Return `not_food: true` for non-food images.
- Per-item JSON: `name, aliases[], cuisine, is_composite_dish, components[], portion{amount, unit, est_grams}, est_nutrients{kcal, protein_g, carbs_g, fat_g, sugar_g, sodium_mg, fibre_g}, confidence`. The model's own nutrient estimate is used only if the database lookup fails.
- Validate with Pydantic. On invalid JSON, retry once with "return valid JSON only". Free models are weaker at strict JSON, so parsing must be tolerant: strip code fences and extract the first JSON object.
- Low confidence (<0.5) still logs automatically (per D6) but the item gets a ⚠ badge so the user knows to check it.

**C4. Typed-input NLP**
- A text LLM call (same OpenRouter chain) converts free text into the same `items[]` schema. It handles quantities ("2 pieces"), modifiers ("less rice", "no sugar", "extra egg") and Singlish drink codes (kopi-o kosong, teh-c siew dai).
- From there it shares the resolver and calculator with the photo path.

**C5. Nutrition data layer**
- `scripts/ingest_sgfoodid.py` (run locally): you download the SG FoodID file(s) from HPB into `data/raw/sgfoodid/` (see Part 3). The script inspects the columns, applies a column-mapping config, normalises everything into `food_reference`, and upserts into Supabase. It is idempotent and prints a load report.
- `scripts/ingest_usda.py` (run locally): loads the USDA bulk CSVs from `data/raw/usda/` (Foundation, SR Legacy, optionally FNDDS) into `food_reference`. It keeps only names and the 7 tracked nutrients so the data fits Supabase's free 500 MB database. Local USDA data means most lookups need no API call. The live USDA API is used only as a last fallback.
- `food_reference(id, source, source_id, name, aliases[], food_group, serving_desc, serving_g, per_serving{…7 nutrients}, per_100g{…7 nutrients}, updated_at)` with a `pg_trgm` GIN index on `name` and `aliases`.
- USDA client: free key, 1,000 requests/hour. It prefers Foundation / SR Legacy / Survey (FNDDS) over Branded, and caches every fetched food into `food_reference`.
- Resolver order: SG FoodID exact/alias → SG FoodID trigram ≥ threshold → local USDA trigram → live USDA API → model estimate (`source="estimated"`).
- An optional "LLM picks the best of 5 candidates" step exists behind `RESOLVER_LLM_PICK`, **off by default**, so each meal costs exactly one model call under the 50/day free quota.

**C6. Calculator**
- Pure functions. Uses per-serving values for standard hawker servings and scales by portion. Otherwise uses per-100g × grams / 100.
- Modifier handling: "less rice" uses an HPB variant if one exists, otherwise a configurable rice reduction. "Kosong" or "no sugar" uses the matching drink variant.
- Stores unrounded values; displays kcal rounded to the nearest 5.

**C7. Profile & target calculation**
- Profile fields: sex, birth year, height (cm), weight (kg), activity level (sedentary 1.2 / light 1.375 / moderate 1.55 / active 1.725 / very active 1.9), goal (lose / maintain / gain).
- BMR uses Mifflin-St Jeor. TDEE = BMR × activity factor. Target = TDEE − 500 (lose), +0 (maintain), or +300 (gain); these adjustments are configurable. Macro targets default to 30% protein / 40% carbs / 30% fat; sugar and sodium use guideline caps.
- The target is recalculated whenever the profile changes. A "set target manually" override is also available.
- Onboarding asks for these fields on first login.

**C8. Meal log & daily tally**
- Tables: `profiles`, `meals(id, user_id, eaten_at_utc, local_date, meal_type, input_type photo|text, note)`, `meal_items(id, meal_id, name, food_ref_id, source, grams, servings, 7 nutrient columns, confidence, model_raw_json, user_edited)`.
- `local_date` is computed on write from the user's timezone. Midnight is the boundary.
- `daily_summary(user, date)` always uses a SUM over rows (no stored running totals), so edits and deletes stay consistent. It returns totals, targets, remaining, a by-meal breakdown and the item count.
- Meal type is auto-assigned by local time (breakfast <11:00, lunch <15:00, snack <18:00, dinner otherwise). It can be edited.

**C9. Dashboard & history**
- Today: calorie ring (eaten vs target), remaining, macro bars, sugar and sodium vs caps, and a meal list (text only, since no photos are kept).
- History: 7- and 30-day bars with a target line, daily averages, macro averages.
- CSV export for any date range.

**C10. Auth, privacy, limits**
- Supabase Auth with email magic link. **Invite-only:** sign-up is disabled, and you invite people from the Supabase dashboard (or through an `ALLOWED_EMAILS` list).
- Photos are processed in memory and never stored. Logs never include image data.
- **Quota guard for the free tier (50 calls/day per OpenRouter account):**
  - Global daily cap `ANALYZE_DAILY_LIMIT_GLOBAL=45` (leaves headroom for testing and retries), counted in the database and reset at midnight SGT
  - Per-user cap `ANALYZE_DAILY_LIMIT_PER_USER=10`
  - Every analyze (photo or text) costs one call. Retries on another model count too
  - When the cap is reached, the app says "Daily AI limit reached. Use search to add food manually." Manual food search and add still works with no model call
  - The Today screen shows remaining AI logs for the day
- Secrets live in Vercel environment variables. `.env.example` is committed; `.env` is never committed.

**C11. Testing & evaluation**
- Backend tests use pytest: calculator (100% coverage), target calculation, resolver against a fixture of about 20 Singapore dishes, tally around 23:59/00:01 SGT, and auth scoping (user A can never see user B's meals).
- The OpenRouter client is mocked in tests.
- `scripts/eval.py` runs `eval/images/` + `eval/labels.csv` (filename, expected_dish, expected_kcal) through **each** model in the fallback chain and reports recognition accuracy, match accuracy and mean absolute kcal error. Use it to pick the model order.

**C12. Deployment**
- One Vercel project: Vite/React static frontend + `api/` Python functions.
- Supabase project: SQL migrations in `supabase/migrations/` and RLS policies.
- GitHub repo → Vercel auto-deploys from `main`, with preview deploys on PRs.

### 2.3 Free OpenRouter vision models (checked 7 Nov 2026)

| Order | Model ID | Why |
|---|---|---|
| 1 | `google/gemma-4-31b-it:free` | Dense model; image + text; 262K context; strong general vision and multilingual |
| 2 | `nvidia/nemotron-3.5-super-vl:free` | 120B MoE (12B active); built for image understanding and reasoning |
| 3 | `google/gemma-4-26b-a4b-it:free` | Faster MoE variant of Gemma 4; image input |
| 4 | `openrouter/free` | OpenRouter's auto-router; picks any free model that supports image input |

Notes:
- The free catalogue changes often. Models get removed or become paid without warning. Keep the list in an environment variable (`VISION_MODELS`) so it can change without a code change. The eval script (C11) should decide the final order.
- **Free-tier quota is per OpenRouter account, not per user:** 20 requests/minute and **50/day** (this plan stays on the free tier; a one-time $10 purchase would raise it to 1,000/day later). The quota guard in C10 keeps the app inside this.
- Some free endpoints may log prompts for training. **Allowed** for this proof of concept, so in OpenRouter's privacy settings, enable free endpoints that may train on inputs, or most free models won't be offered.

### 2.4 Milestones
| # | Milestone | Outcome |
|---|---|---|
| M0 | Scaffold | In your repo: Vite+React, FastAPI under `api/`, Supabase migrations, `.env.example`, `.gitignore`, CI, first Vercel deploy |
| M1 | Auth & profile | Magic-link login (invite-only), onboarding, target calculation |
| M2 | Data layer | SG FoodID + USDA bulk ingested, USDA API fallback, resolver, food search |
| M3 | Recognition | Photo + text analyze endpoints with fallback chain, auto-logging |
| M4 | Tally & dashboard | Daily summary, today view, edit/undo/delete |
| M5 | History & export | Charts, averages, CSV |
| M6 | Eval & harden | Model eval report, rate limits, error states, README |

---

## Part 3 — Data & keys to get before building

All paths are relative to the root of your new repo. **`data/raw/` and `eval/images/` must be in `.gitignore`**: the files are large, and HPB data shouldn't be redistributed through a repo. The agent adds these entries in M0. Create the folders yourself if you download before M0.

### 3.1 Datasets to download

| # | Dataset | Where to get it | What to download | Save to | Needed by |
|---|---|---|---|---|---|
| 1 | **SG FoodID — food search tool** (HPB, Singapore) | https://pphtpc.hpb.gov.sg/web/sgfoodid/tools/food-search | Export the nutrition data for as many foods as the tool allows. Best case is a bulk/all-foods export; otherwise export **one file per food group** (rice dishes, noodles, beverages, kueh, etc.). Keep whatever format it gives (CSV/XLSX). Choose per-serving **and** per-100g values if offered. | `data/raw/sgfoodid/` (e.g. `sgfoodid_noodles.xlsx`, `sgfoodid_beverages.csv`) | M2 (primary source) |
| 2 | **USDA Foundation Foods** (latest, Dec 2025) | https://fdc.nal.usda.gov/download-datasets — "Foundation Foods", **CSV** | Zip, ~3.4 MB (29 MB unzipped) | Unzip into `data/raw/usda/foundation/` | M2 |
| 3 | **USDA SR Legacy** (Apr 2018, final release) | Same page — "SR Legacy", **CSV** | Zip | Unzip into `data/raw/usda/sr_legacy/` | M2 |
| 4 | **USDA FNDDS 2021–2023** *(optional)* | Same page — "FNDDS", **CSV** | Large: ~64 MB zipped, ~1.6 GB unzipped. Covers mixed/prepared dishes. Skip if disk space is tight | Unzip into `data/raw/usda/fndds/` | M2 (optional) |
| 5 | **Your eval photos** | Your phone | 30–50 photos of meals you actually eat: hawker plates, drinks, home-cooked, snacks. Include a few tricky ones (two dishes on one tray, drinks only, non-food) | `eval/images/` (e.g. `001.jpg`) | M6 |
| 6 | **Eval labels** | You create it | A CSV with columns `filename,expected_dish,expected_kcal`. Take `expected_dish` and `expected_kcal` from the closest SG FoodID entry | `eval/labels.csv` | M6 |

Notes on #1:
- I could confirm SG FoodID offers downloads of nutritional information, but not whether it exports one food at a time or in bulk, or in what format. Open the tool and check before you start. If it's one food at a time, export the ~150–300 dishes you and your friends actually eat rather than everything. The ingestion script is written to accept many small files.
- The ingestion script first prints the columns of whatever you saved and waits for confirmation, so the exact format doesn't need to be known in advance.
- Read HPB's terms of use (https://www.hpb.gov.sg/terms-of-use/) for personal and friends-and-family use. The ingestion step keeps the data inside your private database only.

### 3.2 Folder layout after downloading

```
your-repo/
├── data/
│   └── raw/                  ← gitignored
│       ├── sgfoodid/         ← SG FoodID exports (CSV/XLSX, any number of files)
│       └── usda/
│           ├── foundation/   ← unzipped Foundation Foods CSVs (food.csv, nutrient.csv, food_nutrient.csv, …)
│           ├── sr_legacy/    ← unzipped SR Legacy CSVs
│           └── fndds/        ← optional
└── eval/
    ├── images/               ← gitignored
    └── labels.csv
```

### 3.3 Accounts & keys (sign-ups, not downloads)

| Key | Where to get it | Store in |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter.ai → Keys. Then in **Settings → Privacy**, allow free endpoints that may log/train on inputs | `.env` locally + Vercel → Project → Settings → Environment Variables |
| `USDA_API_KEY` | https://fdc.nal.usda.gov/api-key-signup (free, emailed instantly) | Same |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | supabase.com → New project (pick the Singapore region) → Project Settings → API | Same. The service-role key is server-side only and never goes into the frontend |
| Vercel project | vercel.com → Import your GitHub repo | — |

`.env` is gitignored. The agent creates `.env.example` with every variable name and no values.

---

## Part 4 — Prompt for the coding agent

> Create and clone your repo, download the data in Part 3, then start Claude Code in the repo folder and paste everything in the block below.

````markdown
# Role
You are a senior full-stack engineer. Build "Calorific", a photo-based calorie tracker, in this repository. I have already initialised the repo and its remote: do not run `git init`, create remotes, or change git config. Work milestone by milestone. Commit after each milestone, then stop and report: what was built, how to run/test it, and anything you need from me.

# Goal
Users photograph/upload a meal or type a description. A free vision/text LLM on OpenRouter identifies food items and portions. Nutrients are looked up (Singapore HPB SG FoodID first, then USDA FoodData Central, then the model's own estimate). The meal is logged automatically, and the app shows the user's daily totals against a personal target calculated from their profile.

# DECISIONS (authoritative — do not change without asking)
- Hosting: Vercel (Hobby). Frontend: React + Vite + TypeScript + Tailwind, PWA (installable, mobile-first).
- Backend: Python 3.12, FastAPI deployed as Vercel Python Functions under /api. Pydantic v2.
- Database & auth: Supabase (Postgres + Auth). Email magic link, invite-only (public sign-up disabled; optional ALLOWED_EMAILS check). Row Level Security on all user tables. Enable pg_trgm.
- Migrations: SQL files in supabase/migrations/.
- LLM: OpenRouter (OpenAI-compatible, base_url https://openrouter.ai/api/v1). Use the request-level `models` array for automatic fallback. Model lists from env:
  - VISION_MODELS="google/gemma-4-31b-it:free,nvidia/nemotron-3.5-super-vl:free,google/gemma-4-26b-a4b-it:free,openrouter/free"
  - TEXT_MODELS (default to the same list)
  Send HTTP-Referer and X-Title headers. Handle 429/402/5xx: try the next model; surface a friendly "service busy" error if all fail.
  FREE TIER ONLY (proof of concept): the OpenRouter account allows 50 requests/day in total. Providers that log prompts are allowed.
- Recognition: general multimodal LLM with a strict JSON schema; tolerant parsing (strip code fences, extract first JSON object); one retry on invalid JSON.
- Portions: FULLY AUTOMATIC — analyze endpoints save the meal immediately. Frontend shows a result card with Edit and Undo (10s) actions; meals and items are editable/deletable at any time.
- Nutrients tracked: kcal, protein_g, carbs_g, fat_g, sugar_g, sodium_mg, fibre_g.
- Daily target: calculated. Mifflin-St Jeor BMR × activity factor (1.2/1.375/1.55/1.725/1.9); goal adjustment lose −500 / maintain 0 / gain +300 (configurable); macro split default 30P/40C/30F; sugar & sodium guideline caps; manual override allowed. Onboarding collects sex, birth year, height_cm, weight_kg, activity, goal, timezone (default Asia/Singapore).
- Photos: processed in memory only, never stored or logged. Client strips EXIF and resizes to ≤1280px JPEG (≤1 MB) before upload (Vercel 4.5 MB body limit).
- Typed input: free text → LLM parse into the same items schema (handles quantities, "less rice", "no sugar", Singapore drink codes like kopi-o kosong, teh-c siew dai) → same resolver/calculator.
- No barcode scanning.
- Day boundary: midnight in the user's timezone; store eaten_at_utc and computed local_date.
- History: 7/30-day charts with target line, averages, CSV export.
- Quota guard: every analyze (photo or text) = exactly one model call; retries count. Global daily cap ANALYZE_DAILY_LIMIT_GLOBAL (default 45) and per-user cap ANALYZE_DAILY_LIMIT_PER_USER (default 10), counted in Postgres and reset at midnight SGT. At the cap, return a clear "daily AI limit reached" error; manual food search/add keeps working. Today screen shows remaining AI logs. RESOLVER_LLM_PICK defaults to false so the resolver never spends model calls.
- Model call timeout 60s.
- Data files: raw datasets live in data/raw/sgfoodid/ and data/raw/usda/{foundation,sr_legacy,fndds}/; eval photos in eval/images/ with eval/labels.csv. Add data/raw/ and eval/images/ to .gitignore in M0.

# Data model (Postgres)
- profiles(user_id PK → auth.users, display_name, sex, birth_year, height_cm, weight_kg, activity_level, goal, timezone, target_kcal, target_protein_g, target_carbs_g, target_fat_g, cap_sugar_g, cap_sodium_mg, target_override bool, created_at, updated_at)
- food_reference(id, source enum[sgfoodid, usda, estimated], source_id, name, aliases text[], food_group, serving_desc, serving_g, per_serving jsonb, per_100g jsonb, updated_at) + trigram GIN indexes on name/aliases. Readable by all authenticated users; writable by service role only.
- meals(id, user_id, eaten_at_utc, local_date, meal_type enum[breakfast, lunch, snack, dinner], input_type enum[photo, text], note, created_at)
- meal_items(id, meal_id, name, food_ref_id nullable, source, grams, servings, kcal, protein_g, carbs_g, fat_g, sugar_g, sodium_mg, fibre_g, confidence, model_raw_json jsonb, user_edited bool)
- usage_counters(user_id, local_date, analyze_count)
RLS: users can only access their own profiles/meals/meal_items/usage rows.

# API
- POST /api/analyze/photo (multipart image, note?) → saved Meal + DailySummary
- POST /api/analyze/text ({text}) → saved Meal + DailySummary
- PATCH /api/meals/{id}; DELETE /api/meals/{id}
- PATCH /api/meal-items/{id} (swap food_ref_id, change grams/servings) ; DELETE /api/meal-items/{id}
- GET /api/days/{yyyy-mm-dd}/summary
- GET /api/history?from&to ; GET /api/export.csv?from&to
- GET /api/foods/search?q=
- GET/PUT /api/profile (PUT recalculates targets unless override)
All endpoints verify the Supabase JWT and scope by user_id.

# Components & acceptance criteria
C1 Capture UI — Take photo / Upload / Type it; client resize + EXIF strip; progress + error states. Accept: 12MP photo uploads ≤1 MB.
C2 Vision service (api/services/vision.py) — Singapore-aware prompt: list every food/drink, prefer HPB-style dish names, one composite item per standard hawker plate/bowl, estimate grams using plate/utensil scale, note drink sugar level, return {"not_food": true} for non-food. Item schema: name, aliases[], cuisine, is_composite_dish, components[], portion{amount, unit, est_grams}, est_nutrients{7 nutrients}, confidence 0–1. Provider behind an LLMProvider interface.
C3 Text parser (api/services/text_parse.py) — same output schema.
C4 Ingestion (scripts/ingest_sgfoodid.py) — reads files in data/raw/sgfoodid/; FIRST print the columns and a sample and stop for my confirmation; then use a YAML column map; normalise to food_reference; idempotent upsert; load report.
C5 USDA — scripts/ingest_usda.py loads bulk CSVs from data/raw/usda/ (Foundation, SR Legacy, FNDDS if present; skip missing folders) into food_reference, keeping only description + the 7 tracked nutrients per 100g (stay well under Supabase's 500 MB free limit; print row counts and DB size). api/services/usda.py is the live API fallback: key USDA_API_KEY; prefer Foundation/SR Legacy/Survey (FNDDS); cache results into food_reference; backoff on 429.
C6 Resolver (api/services/resolver.py) — SG FoodID exact/alias → SG FoodID pg_trgm similarity ≥ RESOLVER_THRESHOLD → local USDA pg_trgm → live USDA API → model estimate (source=estimated). Optional LLM pick-from-top-5 behind RESOLVER_LLM_PICK (default false). Accept: fixture of ~20 SG dishes resolves correctly.
C7 Calculator (api/services/calc.py) — pure; per-serving for standard servings × portion; else per_100g × grams/100; modifiers (less rice, kosong/no sugar) via variants or config. 100% test coverage.
C8 Targets (api/services/targets.py) — formulas above; unit tests with known values.
C9 Tally (api/services/tally.py) — SUM-based daily summary: totals, targets, remaining, by_meal, item_count. Tests for 23:59/00:01 SGT, edits, deletes.
C10 Frontend pages — Login (magic link), Onboarding, Today (calorie ring, macro bars, sugar/sodium vs caps, meal list, result card with Edit/Undo, ⚠ badge when confidence <0.5 or source=estimated), Edit meal (search & swap food, adjust portion), History (7/30-day charts, averages, CSV export), Profile/Settings.
C11 Security — secrets only in env (OPENROUTER_API_KEY, VISION_MODELS, TEXT_MODELS, USDA_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, ALLOWED_EMAILS, ANALYZE_DAILY_LIMIT_GLOBAL, ANALYZE_DAILY_LIMIT_PER_USER, RESOLVER_THRESHOLD, RESOLVER_LLM_PICK); .env.example committed; reject non-images and files >1.5 MB server-side; never log image bytes.
C12 Tests & eval — pytest (mock OpenRouter), Vitest for frontend logic, test that user A cannot read user B's data. scripts/eval.py runs eval/images + eval/labels.csv (filename, expected_dish, expected_kcal) through EACH model in VISION_MODELS and reports recognition accuracy, resolver accuracy, mean absolute kcal error, latency, and failure rate.
C13 Deploy — vercel.json routing /api/* to Python functions, static frontend; GitHub → Vercel auto-deploy; README covering: Supabase setup + migrations, inviting users, OpenRouter key + privacy setting (and the 50/day free limit), USDA key, the data folder layout + running both ingestion scripts, local dev (vercel dev), running eval.

# Milestones (stop and report after each)
M0 Scaffold + .gitignore + first deploy → M1 Auth, onboarding, targets → M2 Data layer (SG FoodID + USDA ingest, USDA API fallback, resolver, search) → M3 Recognition (photo + text, fallback chain, auto-log) → M4 Today dashboard, edit/undo/delete → M5 History & CSV → M6 Eval, rate limits, error states, README.

# Constraints
- Keep dependencies minimal; typed code; small modules; docstrings on services.
- Ask before adding any paid service or changing a DECISION.
- If an OpenRouter model ID in the list no longer exists, tell me and suggest a current free vision model rather than silently substituting.
- During development, mock OpenRouter by default so testing doesn't burn the 50/day quota; make real calls only when I ask or in scripts/eval.py.
````
