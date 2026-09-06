---
name: mento-deploy
description: >-
  Use when the user wants to deploy Mento.AI to production — either the
  frontend to Vercel or the backend to Render.com. Covers the two-platform
  architecture, environment setup, and step-by-step deployment instructions.
---

# Deploy Mento.AI to Production

## Architecture Reminder

```
Vercel (frontend)                   Render.com (backend)
mento-ai-2.vercel.app               mento-ai-backend.onrender.com
├── index.html                       ├── FastAPI + Uvicorn
├── css/style.css                    ├── SBERT (all-MiniLM-L6-v2)
└── js/app.js                        ├── FAISS
                  API calls ───────→ ├── RapidOCR
                                     └── python run.py
```

> Vercel's Python size limit is 250MB. SBERT + FAISS ≈ 500MB+, so the backend must stay on Render (no Python size limit on free tier).

---

## Part A: Deploy Backend to Render.com

### First-time setup
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect the GitHub repo (ensure `D:\Mento.AI` is pushed to GitHub)
3. Settings:
   - **Root Directory**: *(leave blank — project root)*
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run.py`
   - **Python Version**: 3.11+
4. Click **Deploy**

### Environment Variables on Render
No env vars needed for basic operation. Add if integrating external APIs.

### Updating backend
```powershell
# Push latest changes
git add backend/
git commit -m "feat: update backend"
git push origin main
```
Render auto-deploys on push to `main`.

### Checking Render logs
In the Render dashboard → your service → **Logs** tab. Look for:
```
INFO:     Application startup complete.
INFO:faiss.loader: Successfully loaded faiss.
```

---

## Part B: Deploy Frontend to Vercel

### First-time setup
1. Go to [vercel.com](https://vercel.com) → New Project → import GitHub repo
2. Settings:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Other
   - **Build Command**: *(leave blank — static files)*
   - **Output Directory**: `.` *(the frontend/ folder itself)*
3. Click **Deploy**

### Updating frontend
```powershell
git add frontend/
git commit -m "feat: update frontend"
git push origin main
```
Vercel auto-deploys on push.

### Point frontend at Render backend

In `frontend/js/app.js`, the API base URL is:
```js
const API_BASE = window.location.origin;
```

For the Vercel deployment, this will be `https://mento-ai-2.vercel.app` — which won't have the API routes. Change it to:
```js
const API_BASE = window.location.hostname === 'localhost'
  ? window.location.origin
  : 'https://mento-ai-backend.onrender.com';
```

This makes local dev hit localhost and production hit Render.

---

## Part C: Pre-Deployment Checklist

```powershell
# 1. Ensure requirements.txt is up to date
backend\.venv\Scripts\python.exe -m pip freeze | Out-File requirements.txt -Encoding UTF8

# 2. Run server locally and do a test extraction
backend\.venv\Scripts\python.exe run.py

# 3. Confirm no syntax errors
backend\.venv\Scripts\python.exe -m py_compile backend/main.py backend/core/matcher.py backend/core/parser.py

# 4. Push to GitHub
git status
git add -A
git commit -m "deploy: ready for production"
git push origin main
```

## CORS Note

`main.py` already has:
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```
This allows the Vercel frontend to call the Render backend. In production, consider restricting to `https://mento-ai-2.vercel.app`.
