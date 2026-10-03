# Deployment

**Backend -> Render** (`render.yaml` at the repo root, "New > Blueprint").

- Build: `pip install -r server/requirements.txt && python ml/train.py`. The serving model is **trained during the build** from the
  committed `ml/data/dataset.jsonl`, with pinned library versions, so the pickle always matches the installed scikit-learn/LightGBM.
  (`ml/artifacts/*.joblib` stays gitignored.) Training takes about a minute.
- Start: `cd server && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Health check: `/health`.
- `/content/*.json` (problems, misconceptions) and `/docs/metrics.*` are read from the repo checkout, so they ship with the service.
- CORS: `localhost` dev ports and any `https://*.vercel.app` origin are allowed by default. For a custom domain set
  `CORS_ORIGINS=https://your.domain` (comma-separated) in the Render dashboard.
- **AI hints (optional)**: set `GEMINI_API_KEY` in the Render dashboard (it is `sync: false`, so it is never stored in git). Without it the Hint button works with built-in hints.
- Learner history uses SQLite at `/tmp/relearn.db` (free plan has no persistent disk), so it resets on redeploy/restart.
  Attach a disk and point `RELEARN_DB` at it, or move to Postgres, for persistence.
- The code sandbox is a subprocess with a 2 s timeout and restricted builtins - fine for a demo, **not** hardened against a hostile public.

**Frontend -> Vercel**: import the repo, set *Root Directory* = `client`, framework = Vite, and add the env var
`VITE_API_URL=https://<your-service>.onrender.com`. `client/vercel.json` rewrites all paths to `index.html` so `/dashboard` and `/eval` deep links work.
The first request after idle on Render's free plan takes ~30-60 s while the service wakes up.

**Optional baseline**: `cd ml && python baseline.py` (needs `GEMINI_API_KEY` in `ml/.env`) refreshes `docs/baseline.json` and the
"Our model vs Gemini baseline" table; commit the result. Without a key the Eval page shows "baseline not run".
