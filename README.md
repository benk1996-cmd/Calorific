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

## M1: auth & profile
- Magic-link login with `shouldCreateUser: false`. Invite users in Supabase → Authentication → Users → Invite, and disable public sign-ups (Auth → Providers → Email → "Allow new users to sign up" off). Optionally set `ALLOWED_EMAILS`.
- The API validates each bearer token against `SUPABASE_URL/auth/v1/user`, then scopes all queries by `user_id`.
- In Supabase Auth → URL Configuration, add your Vercel URL and `http://localhost:5173` as redirect URLs.
