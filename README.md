# 🧠 Mento.AI — AI-Powered Syllabus Notes Extractor

> Upload your study material. Paste your syllabus. Get perfectly organized, topic-by-topic notes — zero data loss.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python)](https://www.python.org)
[![Vercel](https://img.shields.io/badge/Deployment-Vercel%20Serverless-black?style=flat&logo=vercel)](https://vercel.com)
[![SBERT](https://img.shields.io/badge/SBERT-all--MiniLM--L6--v2-orange?style=flat)](https://www.sbert.net)
[![Scikit-Learn](https://img.shields.io/badge/Matcher-TF--IDF%20%2B%20Cosine-F7931E?style=flat&logo=scikit-learn)](https://scikit-learn.org)

---

## 🚀 Live Demo

| Surface | URL |
|---|---|
| 🌐 **Live Web Application** | [mento-ai-iota.vercel.app](https://mento-ai-iota.vercel.app) |
| 🔧 **API Health Endpoint** | [mento-ai-iota.vercel.app/api/health](https://mento-ai-iota.vercel.app/api/health) |

---

## 📖 What It Does

**Mento.AI** automatically parses, aligns, and summarizes course materials based on your syllabus structure:

1. **Extracts Content**: Parses PDFs (digital & scanned OCR), Word documents (`.docx`), plain text (`.txt`), and scanned note images.
2. **Understands Syllabus Hierarchy**: Automatically detects Units, Sections, Chapters, and hierarchical bullet points.
3. **Semantic Topic Matching**: Maps each syllabus topic to relevant study excerpts using **Hybrid Semantic Matching** (SBERT + FAISS vector search in dedicated mode, and sub-50ms TF-IDF N-gram Cosine Similarity on Serverless).
4. **Coverage Audit**: Calculates syllabus coverage percentage, highlights covered topics, and flags missing topics.
5. **Zero Data Loss**: Gathers any unmatched handwritten notes and study content into an **"Extracted Study Notes (Uncategorized)"** section.
6. **Compiles Output**: Exports an organized, clean Word (`.docx`) or PDF document formatted by unit and topic.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5 · CSS3 (Neural Indigo Glassmorphism) · Vanilla JavaScript |
| **Backend** | Python 3.12 · FastAPI · Uvicorn |
| **Serverless Routing** | Vercel Serverless Functions (`api/*.py`) |
| **Semantic AI Engine** | `sentence-transformers` (all-MiniLM-L6-v2) · `faiss-cpu` · `scikit-learn` |
| **OCR & Text Cleanup** | `rapidocr-onnxruntime` · Contrast adaptive filter · Post-processor regex unwrap |
| **Document Parsers** | `pymupdf` (fitz) · `python-docx` · `docx2python` |
| **Document Generators** | `python-docx` (Word) · `reportlab` (PDF) |
| **Real-Time Streaming** | Server-Sent Events (SSE) & Fail-Safe Polling Fallback |

---

## 📁 Repository Layout

```text
Mento.AI/
├── run.py                    ← Local development server entrypoint (http://localhost:8000)
├── requirements.txt          ← Optimized Python dependencies (<85MB serverless bundle)
├── vercel.json               ← Vercel serverless configuration & rewrites
├── .python-version           ← Pinned Python version (3.12)
│
├── api/                      ← Vercel Serverless Function entrypoints
│   ├── index.py              ← Core FastAPI catch-all handler
│   ├── upload.py             ← POST /api/upload handler
│   ├── health.py             ← GET /api/health handler
│   ├── process.py            ← GET /api/process/{task_id} progress streaming
│   ├── results.py            ← GET /api/results/{task_id} preview payload
│   ├── generate.py           ← POST /api/generate/{task_id} DOCX/PDF compiler
│   └── download.py           ← GET /api/download/{task_id} export download
│
├── frontend/                 ← Frontend source directory
│   ├── index.html            ← Single-page application (4 stages)
│   ├── css/style.css         ← Neural Indigo design system (aurora glassmorphism)
│   └── js/app.js             ← Frontend application controller
│
├── public/                   ← Vercel zero-config static directory (mirrors frontend)
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
│
├── backend/
│   ├── main.py               ← FastAPI app, CORS, routes, and background pipeline
│   ├── core/
│   │   ├── parser.py         ← Text extraction for PDF, DOCX, TXT, Images
│   │   ├── syllabus_parser.py← Regex & structure parsing for syllabus topics
│   │   ├── matcher.py        ← Hybrid SBERT + FAISS / TF-IDF Semantic Matcher
│   │   ├── docx_generator.py ← Word (.docx) and PDF document compiler
│   │   ├── ocr_engine.py     ← RapidOCR & Tesseract optical character recognition
│   │   ├── handwriting_ocr.py← Preprocessing filter for scanned handwritten pages
│   │   ├── post_processor.py ← OCR spelling correction and line wrap unwrap
│   │   └── math_parser.py    ← LaTeX formula extraction and normalization
│   └── utils/
│       └── file_utils.py     ← Task directories, UUID generation, /tmp storage
│
└── .agents/                  ← Workspace configuration & agent skills
    └── GEMINI.md             ← Coding standards, CSS tokens, and API contracts
```

---

## 💻 Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/UNNIKRISHNAN-NEXUS/Mento.AI.git
cd Mento.AI
```

### 2. Create and Activate Virtual Environment
```bash
# On Windows
python -m venv backend\.venv
backend\.venv\Scripts\activate

# On macOS/Linux
python3 -m venv backend/.venv
source backend/.venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the Development Server
```bash
python run.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## ⚡ Vercel Deployment (All-in-One)

Mento.AI is fully optimized to deploy both the **Frontend and Backend on Vercel** under a single project:

### Option A: Automatic Git Integration (Recommended)
1. Push your repository to GitHub.
2. Go to the **[Vercel Dashboard](https://vercel.com/dashboard)** and click **"Add New Project"**.
3. Import your `Mento.AI` repository.
4. Leave all build settings at **Default (Zero Config)**.
5. Click **Deploy**.

### Option B: Deploy via Vercel CLI
```bash
# Install and run Vercel CLI
npx vercel --prod
```

---

## 📡 API Reference

### 1. `POST /api/upload`
Uploads study documents and syllabus (file or raw text).
- **Body (`multipart/form-data`)**:
  - `study_material`: File list (`.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.webp`)
  - `syllabus`: Syllabus file (optional)
  - `syllabus_text`: Plain text syllabus (optional)
  - `threshold`: Similarity threshold float (`0.1` – `0.9`, default: `0.35`)
  - `math_mode`: Extract formulas (`true`/`false`)
  - `handwriting_mode`: Multi-pass handwriting OCR (`true`/`false`)
- **Response (`200 OK`)**:
  ```json
  {
    "task_id": "b0dfd10f-4cdf-40d4-b4d4-0b8c9d7a371e",
    "results": { ... } // Directly provided in serverless environments
  }
  ```

### 2. `GET /api/process/{task_id}`
Returns live Server-Sent Events (SSE) stream or JSON progress updates:
```json
{
  "status": "Matching completed successfully!",
  "progress": 100
}
```

### 3. `GET /api/results/{task_id}`
Retrieves extracted topics, excerpts, confidence scores, and coverage audit.

### 4. `POST /api/generate/{task_id}`
Compiles document in requested format.
- **Body (`application/json`)**:
  ```json
  {
    "topics": [ ... ],
    "export_format": "docx" // or "pdf"
  }
  ```
- **Response**:
  ```json
  {
    "download_url": "/api/download/b0dfd10f-4cdf-40d4-b4d4-0b8c9d7a371e?format=docx",
    "format": "docx"
  }
  ```

### 5. `GET /api/download/{task_id}?format=docx|pdf`
Downloads the compiled Word or PDF document.

### 6. `GET /api/health`
Health check endpoint returning server status and OCR engine availability.

---

## 📄 License

MIT License © 2026 Mento.AI. Developed with ❤️ for students, educators, and lifelong learners.
