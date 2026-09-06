# Mento.AI — Project Rules for Antigravity IDE

## Project Overview

**Mento.AI** is a full-stack AI web application that:
- Accepts study material documents (PDF, DOCX, TXT, scanned images)
- Accepts a syllabus (file or pasted text)
- Uses SBERT semantic matching + FAISS vector search to map study content to syllabus topics
- Compiles everything into a downloadable Word (.docx) or PDF — organized by topic

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Plain HTML + CSS + Vanilla JS (no framework) |
| Backend | Python 3 · FastAPI · Uvicorn |
| AI Engine | `sentence-transformers` (all-MiniLM-L6-v2) + `faiss-cpu` |
| OCR | `rapidocr-onnxruntime` |
| PDF parsing | `pymupdf` (fitz) |
| DOCX r/w | `python-docx` |
| Progress streaming | Server-Sent Events (SSE) |

---

## Repository Layout

```
D:\Mento.AI\
├── run.py                         ← Server entrypoint: python run.py → http://localhost:8000
├── requirements.txt               ← Python dependencies
├── vercel.json                    ← Vercel deployment config (frontend only)
│
├── frontend/                      ← Static files served by FastAPI at /
│   ├── index.html                 ← Single-page app (4 stages: upload/processing/preview/download)
│   ├── css/style.css              ← Neural Indigo design system (glassmorphism + aurora)
│   └── js/app.js                  ← All frontend logic (file upload, SSE, accordion, export)
│
├── backend/
│   ├── main.py                    ← FastAPI app + all API routes
│   ├── core/
│   │   ├── parser.py              ← Text extraction: PDF→PyMuPDF, DOCX→python-docx, images→RapidOCR
│   │   ├── syllabus_parser.py     ← Parses syllabus into structured topic list
│   │   ├── matcher.py             ← SBERT encoding + FAISS search → match result dicts
│   │   ├── docx_generator.py      ← Builds the final Word/PDF output document
│   │   ├── ocr_engine.py          ← RapidOCR wrapper for image/scanned content
│   │   └── math_parser.py         ← LaTeX/formula extraction helper
│   └── utils/
│       └── file_utils.py          ← task_id generation, upload/output path helpers
│
├── api/
│   └── index.py                   ← Vercel serverless entrypoint (wraps backend)
│
├── backend/.venv/                 ← Python virtualenv — always use this Python
│   └── Scripts/python.exe         ← Use: backend\.venv\Scripts\python.exe
│
└── .agents/                       ← Antigravity IDE workspace customizations (this folder)
```

---

## Critical Rules — Always Follow

### Python Environment
- **Always use the project venv**: `backend\.venv\Scripts\python.exe` — never `python` or global pip
- **Pip installs**: `backend\.venv\Scripts\python.exe -m pip install <pkg>`
- Run the server from the **project root** (`D:\Mento.AI`), never from a subdirectory

### Backend Coding Standards
- Every API route lives in `backend/main.py`
- All AI logic lives in `backend/core/` — keep modules focused (one concern per file)
- Background pipeline: `run_extraction_pipeline()` runs synchronously via `BackgroundTasks`
- In-memory state: `tasks_progress` and `tasks_results` dicts (keyed by `task_id`)
- Use `logger = logging.getLogger("module_name")` in every core module

### API Contract — Do Not Break These
| Endpoint | Method | Key fields |
|---|---|---|
| `/api/upload` | POST (multipart) | `study_material` (files), `syllabus` or `syllabus_text`, `threshold`, `math_mode`, `handwriting_mode` |
| `/api/process/{task_id}` | GET SSE | Emits `{ status: str, progress: int }` — 100 = done, -1 = error |
| `/api/results/{task_id}` | GET | Returns `{ topics, coverage, study_file, syllabus_file }` |
| `/api/generate/{task_id}` | POST JSON | Body: `{ topics: [...], export_format: "docx"|"pdf" }` |
| `/api/download/{task_id}` | GET | Query param: `?format=docx|pdf` |

### Matcher Output Schema
Every item in `topics[].matches[]` must have these fields:
```json
{ "chunk_id", "text", "page_number", "type", "source",
  "score", "similarity_score", "confidence_pct" }
```
`similarity_score` is required — `app.js` renders it in the Preview accordion.

### Frontend Coding Standards
- **No frameworks** — plain JS only, no React/Vue/jQuery
- All app state lives in module-level `let` vars in `app.js`: `studyFiles`, `syllabusFile`, `syllabusMode`, `taskId`, `rawResults`
- Stage switching: `showStage(stageElement)` — removes `active` from all 4 stages, adds it to the target
- File badge: add/remove `.show` class (not `.visible`)
- Drag-over: add/remove `.dragover` class (not `.drag-over`)
- CSS design token variables are in `:root` in `style.css` — always use them, never hardcode colors

### CSS Design System — Neural Indigo
| Variable | Value | Usage |
|---|---|---|
| `--bg` | `#070814` | Page background |
| `--indigo` | `#6366f1` | Primary color |
| `--violet` | `#a855f7` | Secondary color |
| `--cyan` | `#06b6d4` | Accent color |
| `--green` | `#10b981` | Success state |
| `--text` | `#f0f0ff` | Body text |
| `--muted` | `#94a3b8` | Secondary text |
| `--font-h` | Outfit | Headings |
| `--font-b` | Inter | Body |
| `--blur` | `blur(24px)` | Glassmorphism |
| `--radius` | `20px` | Card border radius |

---

## Deployment Architecture

```
Vercel (frontend only)         Render.com (backend Python AI)
https://mento-ai-2.vercel.app  https://mento-ai-backend.onrender.com
  └─ Serves: index.html,          └─ Runs: FastAPI + SBERT + FAISS
             style.css, app.js        Start: python run.py
```

**Why 2 platforms?** Vercel Python limit is 250MB. SBERT + FAISS = 500MB+.

### Vercel Config (`frontend/vercel.json`)
Serves only the static frontend. API calls must target the Render backend URL (configured in `app.js` API_BASE).

---

## Formatting & Quality

- Python: follow PEP 8, use type hints on all public functions
- Docstrings: use the existing triple-quoted style in each module
- Keep `# -*- coding: utf-8 -*-` header on all Python files
- HTML: use semantic tags, keep aria labels on interactive elements
- CSS: group rules by section with `/* ─── Section Name ─── */` comments
- Never leave dead code — remove rather than comment out
