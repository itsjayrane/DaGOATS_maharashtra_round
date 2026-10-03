# Deployment

**Backend -> Render** (`render.yaml` at the repo root, "New > Blueprint").

- Build: `pip install -r server/requirements.txt && cd server && python -m app.artifacts`. **No training in the build**: the serving
  model `ml/artifacts/diagnoser.joblib` (3 MB, with its calibration temperature) and `ml/artifacts/threshold.json` are **committed**.
  They were trained with exactly the pinned `ml/requirements.txt` versions, which are recorded inside the model file.
  `python -m app.artifacts` checks that every required file exists and that the model loads. A failed check fails the build,
  so the previous deploy stays live.
- Startup runs the same check and **refuses to start**, listing every missing file and the fix, rather than serving without a model.
- To change the model: `cd ml && python -m relearn_ml.generate && python train.py` (deterministic), then commit `ml/artifacts/` and `docs/`.
  The evaluation scripts (`ml/eval_unseen.py`, `ml/eval_models.py`) are **not** part of the build; their outputs in `docs/*.json` are committed.
- Start: `cd server && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Health check: `/health`.
- `content/*.json` and `docs/*.json` are read from the repo checkout, so they ship with the service.
- No API keys are needed. The only optional external call is the drafting LLM for "Practise your own question" (`LLM_*` below); with those unset the app makes no external calls.
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
| `LLM_BASE_URL` | optional, e.g. `https://api.groq.com/openai/v1` | OpenAI-compatible endpoint that drafts "own question" problems |
| `LLM_MODEL` | optional, e.g. `llama-3.3-70b-versatile` | model name at that provider |
| `LLM_API_KEY` | optional, secret | the provider key (Render dashboard only - `sync: false`, never committed). All three set = feature on |

**Frontend -> Vercel**: import the repo, set *Root Directory* = `client`, framework = Vite, and **do not set `VITE_API_URL`**.
The production build then calls `/api/...` on its own origin, and `client/vercel.json` rewrites `/api/:path*` to
`https://relearn-api-jfka.onrender.com/:path*` (change it if your Render URL differs) before the SPA fallback that serves
`index.html` for `/dashboard`, `/teach`, `/insights` and `/eval`. Same-origin calls are not blocked by ad blockers. Vercel's proxy has a
request time limit, so slow calls are budgeted (drafting: 20 s in total). The first request after idle on Render's free plan takes ~30-60 s while the service wakes up;
the app shows a "Waking the server…" banner until `/health` answers.
