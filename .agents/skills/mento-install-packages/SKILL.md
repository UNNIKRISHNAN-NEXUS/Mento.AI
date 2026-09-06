---
name: mento-install-packages
description: >-
  Use when the user wants to install a new Python package for the Mento.AI
  backend, update requirements.txt, or troubleshoot missing module errors.
  Always uses the project virtual environment at backend/.venv/
---

# Install Python Packages for Mento.AI

## Always Use the Project Venv

```powershell
# Install a package
backend\.venv\Scripts\python.exe -m pip install <package-name>

# Install with a specific version
backend\.venv\Scripts\python.exe -m pip install "sentence-transformers>=2.7"

# Install all project dependencies (from requirements.txt)
backend\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Update `requirements.txt` After Installing

```powershell
backend\.venv\Scripts\python.exe -m pip freeze > requirements.txt
```

Or manually add just the new package with its version:
```powershell
backend\.venv\Scripts\python.exe -c "import importlib.metadata; print(importlib.metadata.version('package-name'))"
```

## Verify Installation

```powershell
backend\.venv\Scripts\python.exe -c "import package_name; print('OK:', package_name.__version__)"
```

## Key Packages Already Installed

| Package | Import name | Purpose |
|---|---|---|
| `fastapi` | `fastapi` | Web framework |
| `uvicorn` | `uvicorn` | ASGI server |
| `sentence-transformers` | `sentence_transformers` | SBERT embeddings |
| `faiss-cpu` | `faiss` | Vector index search |
| `pymupdf` | `fitz` | PDF text extraction |
| `python-docx` | `docx` | Read/write DOCX |
| `rapidocr-onnxruntime` | `rapidocr_onnxruntime` | OCR for images |
| `numpy` | `numpy` | Array math |
| `aiofiles` | `aiofiles` | Async file I/O |

## Common Errors

| Error | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'X'` | `backend\.venv\Scripts\python.exe -m pip install X` |
| `pip: command not found` | Use full path: `backend\.venv\Scripts\python.exe -m pip` |
| `ERROR: Could not find a version that satisfies` | Check package name spelling on PyPI |
| Package installs but import still fails | Confirm you're using venv python, not global python |
