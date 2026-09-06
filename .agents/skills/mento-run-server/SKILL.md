---
name: mento-run-server
description: >-
  Use when the user wants to start, restart, or run the Mento.AI local
  development server. Also use when troubleshooting server startup errors,
  checking if the server is running, or verifying the health endpoint.
---

# Run the Mento.AI Development Server

## Prerequisites

Confirm you are in the project root: `D:\Mento.AI`

## Steps

### 1. Start the Server

```powershell
backend\.venv\Scripts\python.exe run.py
```

Expected output:
```
============================================================
  Mento.AI -- AI-Powered Syllabus Notes Extractor
============================================================
  Server starting at: http://localhost:8000
  Press Ctrl+C to stop.
============================================================

INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

> **First run**: Takes ~60 seconds at "Initializing AI semantic models..." while SBERT (`all-MiniLM-L6-v2`, ~90MB) downloads and caches. Every subsequent run starts in ~5 seconds.

### 2. Verify the Server is Healthy

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/health' | ConvertTo-Json
```

Expected: `{ "status": "healthy", "tesseract_ocr_available": false }`

### 3. Open the App

Navigate to: **http://localhost:8000**

## Common Startup Errors

| Error | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Run `backend\.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| `Address already in use (port 8000)` | Kill the existing process: `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F` |
| `ModuleNotFoundError: No module named 'backend'` | You must run from project root `D:\Mento.AI`, not from a subdirectory |
| `faiss.swigfaiss_avx2` warning | Harmless — FAISS falls back to standard build automatically |

## Hot Reload

The server auto-reloads when files in `backend/` change (Uvicorn `--reload` is on). Frontend changes (HTML/CSS/JS) take effect immediately on browser refresh — no restart needed.
