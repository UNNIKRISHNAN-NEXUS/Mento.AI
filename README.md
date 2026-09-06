# 🧠 Mento.AI — AI-Powered Syllabus Notes Extractor

> Upload your study material. Paste your syllabus. Get perfectly organized, topic-by-topic notes — zero data loss.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python)](https://www.python.org)
[![Sentence Transformers](https://img.shields.io/badge/SBERT-all--MiniLM--L6--v2-orange?style=flat)](https://www.sbert.net)
[![FAISS](https://img.shields.io/badge/FAISS-1.7+-blue?style=flat)](https://faiss.ai)

---

## What It Does

Mento.AI is a full-stack AI web application that:

1. **Parses** your study material — PDF, DOCX, TXT, or scanned images (via OCR)
2. **Understands** your syllabus structure — units, topics, hierarchy numbers
3. **Matches** each syllabus topic to relevant study material excerpts using **SBERT semantic embeddings** + **FAISS vector search**
4. **Compiles** everything into a downloadable Word (.docx) or PDF, organized by topic

---

## Live Demo

| Surface | URL |
|---|---|
| 🌐 Frontend | [mento-ai-2.vercel.app](https://mento-ai-2.vercel.app) |
| 🔧 Backend API | [mento-ai-backend.onrender.com](https://mento-ai-backend.onrender.com/api/health) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5 + CSS3 + Vanilla JS (Neural Indigo design system) |
| Backend | Python 3 · FastAPI · Uvicorn |
| AI Engine | `sentence-transformers` (all-MiniLM-L6-v2) + `faiss-cpu` |
| OCR | `rapidocr-onnxruntime` (primary) + pytesseract (fallback) |
| PDF parsing | `pymupdf` (fitz) |
| DOCX r/w | `python-docx` + `docx2python` |
| PDF export | `reportlab` |
| Progress streaming | Server-Sent Events (SSE) |

---

## Repository Layout

```
Mento.AI/
├── run.py                    ← Server entrypoint
├── requirements.txt          ← Python dependencies
├── vercel.json               ← Vercel (frontend-only) deployment config
├── .gitignore
│
├── frontend/                 ← Static files served at /
│   ├── index.html            ← Single-page app (4 stages)
│   ├── css/style.css         ← Neural Indigo design system
│   └── js/app.js             ← All frontend logic
│
├── backend/
│   ├── main.py               ← FastAPI app + all API routes
│   ├── core/
│   │   ├── parser.py         ← PDF / DOCX / TXT / Image text extraction
│   │   ├── syllabus_parser.py← Structured topic extraction from syllabus
│   │   ├── matcher.py        ← SBERT + FAISS semantic matching
│   │   ├── docx_generator.py ← DOCX & PDF output generation
│   │   ├── ocr_engine.py     ← RapidOCR + Tesseract wrapper
│   │   ├── handwriting_ocr.py← Handwriting-tuned OCR preprocessing
│   │   └── math_parser.py    ← LaTeX → Unicode math normalization
│   └── utils/
│       └── file_utils.py     ← Task ID, paths, file cleanup
│
├── api/
│   └── index.py              ← (Legacy Vercel serverless entrypoint — not used)
│
├── backend/.venv/            ← Python virtual environment
└── .agents/                  ← Antigravity IDE workspace configuration
    ├── GEMINI.md             ← Project rules (always-on AI context)
    └── skills/               ← Runbooks for common dev tasks
        ├── mento-run-server/
        ├── mento-add-api-endpoint/
        ├── mento-debug-ai-pipeline/
        ├── mento-deploy/
        ├── mento-add-file-format/
        ├── mento-install-packages/
        └── mento-edit-frontend-ui/
```

---

## Local Development

### Prerequisites

- Python 3.10+
- Git

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-username/mento-ai.git
cd mento-ai

# 2. Create virtual environment
python -m venv backend/.venv

# 3. Install dependencies
backend\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Start the server
backend\.venv\Scripts\python.exe run.py
```

Open **http://localhost:8000** in your browser.

> **First run note:** Takes ~60 seconds at "Initializing AI semantic models..." while SBERT downloads and caches the `all-MiniLM-L6-v2` model (~90MB). Every subsequent run starts in ~5 seconds.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/upload` | `POST` | Upload study files + syllabus, returns `task_id` |
| `/api/process/{task_id}` | `GET` (SSE) | Live progress stream: `{status, progress}` |
| `/api/results/{task_id}` | `GET` | Full match results: `{topics, coverage, ...}` |
| `/api/generate/{task_id}` | `POST` | Generate DOCX/PDF from selected topics |
| `/api/download/{task_id}` | `GET` | Download the generated file |
| `/api/health` | `GET` | Health check |

### Upload Request

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "study_material=@my_textbook.pdf" \
  -F "syllabus_text=Unit 1: Introduction\n1.1 History\n1.2 Concepts" \
  -F "threshold=0.35" \
  -F "math_mode=false" \
  -F "handwriting_mode=false"
```

### SSE Progress

```js
const es = new EventSource('/api/process/TASK_ID');
es.onmessage = e => {
    const { status, progress } = JSON.parse(e.data);
    // progress: 0-100 (done), -1 (error)
};
```

---

## App Flow

```
Upload Stage  →  Processing Stage  →  Preview Stage  →  Download Stage
     │                  │                   │                  │
 Upload files      Live SSE stream     Accordion of        Download
 + syllabus        (SBERT + FAISS)     all topics          DOCX/PDF
                                       with excerpts
```

---

## Supported File Formats

| Format | Study Material | Syllabus |
|---|---|---|
| PDF (digital) | ✅ | ✅ |
| PDF (scanned, OCR) | ✅ | ✅ |
| DOCX | ✅ | ✅ |
| TXT | ✅ | ✅ |
| PNG / JPG / WEBP | ✅ | ✅ |
| Pasted text | — | ✅ |

---

## Deployment

This project uses a **two-platform architecture**:

```
Vercel (frontend)          →    Static HTML/CSS/JS only
Render.com (backend)       →    FastAPI + SBERT + FAISS (AI too large for Vercel)
```

**Why two platforms?** Vercel's Python serverless limit is 250MB. SBERT + FAISS ≈ 500MB+.

See [`.agents/skills/mento-deploy/SKILL.md`](.agents/skills/mento-deploy/SKILL.md) for full deployment instructions.

---

## Antigravity IDE Setup

This project is configured for the **Antigravity AI IDE**. Open `D:\Mento.AI` in Antigravity IDE and the agent will automatically load:

- **Project rules** from `.agents/GEMINI.md` — tech stack, API contract, CSS tokens
- **Skills** from `.agents/skills/` — runbooks for running, debugging, deploying, and extending the app

No setup needed — it just works when you open the project.

---

## License

MIT © 2026 Mento.AI
