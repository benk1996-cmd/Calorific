# Calorific

Photo-based calorie tracker (React/Vite PWA + FastAPI on Vercel + Supabase). See [BUILD_PLAN.md](BUILD_PLAN.md).

## Local dev (M0)
```bash
cp .env.example .env
pip install -r requirements-dev.txt && pytest
uvicorn api.index:app --reload --port 8000   # backend
npm install && npm run dev                    # frontend (proxies /api to :8000)
```
Full setup docs (Supabase, keys, ingestion, eval) are completed in M6.
