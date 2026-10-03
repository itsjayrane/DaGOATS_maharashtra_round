# Deployment

**Backend -> Render** (`render.yaml` at the repo root, "New > Blueprint").

- Build: `pip install -r server/requirements.txt && python ml/train.py`. The serving model is **trained during the build** from the
  committed `ml/data/dataset.jsonl`, with pinned library versions, so the pickle always matches the installed scikit-learn/LightGBM.
  (`ml/artifacts/*.joblib` stays gitignored; `ml/artifacts/threshold.json` is committed and rewritten by the build.) Training takes 1-2 minutes.
  The heavier leave-one-misconception-out evaluation (`ml/eval_unseen.py`) is **not** part of the build; its output `docs/unseen_eval.json` is committed.
- Start: `cd server && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Health check: `/health`.
- `content/*.json` and `docs/*.json` are read from the repo checkout, so they ship with the service.
- No API keys: the app makes no external calls (no LLM).
- CORS: `localhost` dev ports and any `https://*.vercel.app` origin are allowed by default. For a custom domain set
  `CORS_ORIGINS=https://your.domain` (comma-separated) in the Render dashboard.
- Learner history, custom problems and insights use SQLite at `/tmp/relearn.db` (free plan has no persistent disk), so they reset on
  redeploy/restart. Attach a disk and point `RELEARN_DB` at it, or move to Postgres, for persistence.
- The code sandbox is a subprocess with a 2 s timeout, restricted builtins and (on Linux) CPU / memory / file-size limits - fine for a
  demo, **not** hardened against a hostile public.

**Environment variables** (Render dashboard -> Environment)

| Variable | Value | Why |
|---|---|---|
| `INSIGHTS_SALT` | any long random string (the blueprint generates one) | salts the SHA-256 hashes of learner ids on the Insights page and in the CSV export; without it a public dev default is used |
| `RELEARN_SEED_DEMO` | `1` (optional) | seeds a clearly labelled SYNTHETIC learner and class so the Dashboard and Insights are not empty in a demo |

**Frontend -> Vercel**: import the repo, set *Root Directory* = `client`, framework = Vite, and add the env var
`VITE_API_URL=https://<your-service>.onrender.com`. `client/vercel.json` rewrites all paths to `index.html` so `/dashboard`, `/teach`,
`/insights` and `/eval` deep links work. The first request after idle on Render's free plan takes ~30-60 s while the service wakes up;
the app shows a "Waking the server…" banner until `/health` answers.
