# -*- coding: utf-8 -*-
"""
Mento.AI FastAPI Application
Handles multi-file uploads, text syllabus inputs, SSE progress tracking,
preview results, and PDF/DOCX format downloads.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.utils.file_utils import (
    generate_task_id, get_task_paths, clean_old_files, validate_file_extension
)
from backend.core.parser import parse_document
from backend.core.syllabus_parser import parse_syllabus
from backend.core.matcher import match_syllabus_to_document, compute_coverage_audit
from backend.core.docx_generator import generate_docx, generate_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="Mento.AI", description="AI-Powered Syllabus-Based Notes Extractor")

# CORS middleware for local frontend and Vercel same-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory progress and result storage (task_id -> data)
tasks_progress: Dict[str, Dict[str, Any]] = {}
tasks_results: Dict[str, Dict[str, Any]] = {}

# Allowed file extensions
ALLOWED_DOCS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp"}

def run_extraction_pipeline(
    task_id: str,
    study_file_paths: List[str],
    syllabus_file_path: str,
    threshold: float,
    math_mode: bool = False,
    handwriting_mode: bool = False
):
    """
    Background worker pipeline.
    Parses study material files (single or multiple) and syllabus, performs semantic matching.
    """
    try:
        tasks_progress[task_id] = {"status": "Parsing syllabus...", "progress": 10}
        logger.info(f"Task {task_id}: Parsing syllabus...")
        
        # 1. Parse syllabus
        topics = parse_syllabus(syllabus_file_path)
        if not topics:
            raise ValueError("No topics could be extracted from the syllabus.")
            
        tasks_progress[task_id] = {
            "status": f"Syllabus parsed: Found {len(topics)} topics. Parsing study materials...", 
            "progress": 30
        }
        logger.info(f"Task {task_id}: Syllabus parsed. {len(topics)} topics found.")
        
        # 2. Parse study materials (supports multiple files)
        all_chunks = []
        total_files = len(study_file_paths)
        
        for idx, file_path in enumerate(study_file_paths):
            def parser_progress(stage: str, current: int, total: int):
                # Map file index to 30%-65% progress range
                step_pct = 30 + int(((idx + (current / total)) / total_files) * 35)
                tasks_progress[task_id] = {
                    "status": f"[{idx+1}/{total_files}] {stage} ({current}/{total})...",
                    "progress": step_pct
                }
                
            chunks = parse_document(
                file_path, 
                progress_callback=parser_progress,
                math_mode=math_mode,
                handwriting_mode=handwriting_mode
            )
            all_chunks.extend(chunks)
            
        if not all_chunks:
            raise ValueError("No text could be extracted from the uploaded study material(s).")
            
        tasks_progress[task_id] = {
            "status": "Initializing AI semantic models...",
            "progress": 70
        }
        logger.info(f"Task {task_id}: Study materials parsed. Total {len(all_chunks)} chunks pooled.")
        
        # 3. Match syllabus to document using SBERT + FAISS
        matched_results = match_syllabus_to_document(
            topics=topics,
            chunks=all_chunks,
            similarity_threshold=threshold,
            top_k=5
        )
        
        # 4. Compute coverage audit
        coverage_report = compute_coverage_audit(matched_results)
        
        # Store results in-memory
        study_filenames = [os.path.basename(p) for p in study_file_paths]
        tasks_results[task_id] = {
            "topics": matched_results,
            "coverage": coverage_report,
            "study_file": ", ".join(study_filenames),
            "syllabus_file": os.path.basename(syllabus_file_path)
        }
        
        tasks_progress[task_id] = {"status": "Matching completed successfully!", "progress": 100}
        logger.info(f"Task {task_id}: Pipeline finished successfully.")
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        tasks_progress[task_id] = {
            "status": f"Failed: {str(e)}",
            "progress": -1
        }

@app.post("/api/upload")
@app.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    study_material: List[UploadFile] = File(...),
    syllabus: Optional[UploadFile] = File(None),
    syllabus_text: Optional[str] = Form(None),
    threshold: float = Form(0.35),
    math_mode: bool = Form(False),
    handwriting_mode: bool = Form(False)
):
    """
    Upload study material(s) and syllabus (file or raw text).
    Returns a unique task_id.
    """
    clean_old_files()
    
    if not study_material:
        raise HTTPException(status_code=400, detail="Please upload at least one study material file.")
        
    if not syllabus and not syllabus_text:
        raise HTTPException(status_code=400, detail="Please provide a syllabus file or type syllabus text.")
        
    task_id = generate_task_id()
    upload_path, _ = get_task_paths(task_id)
    
    # Save Study Material files (supports multiple)
    saved_study_paths = []
    CHUNK_SIZE = 1024 * 1024
    
    for i, s_file in enumerate(study_material):
        s_ext = os.path.splitext(s_file.filename)[1].lower()
        if s_ext not in ALLOWED_DOCS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{s_file.filename}'. Allowed: {', '.join(ALLOWED_DOCS)}"
            )
            
        file_path = os.path.join(upload_path, f"study_material_{i+1}{s_ext}")
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await s_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                buffer.write(chunk)
        saved_study_paths.append(file_path)
        
    # Save Syllabus file or text
    syllabus_file_path = os.path.join(upload_path, "syllabus.txt")
    
    if syllabus_text and syllabus_text.strip():
        with open(syllabus_file_path, "w", encoding="utf-8") as f:
            f.write(syllabus_text.strip())
    elif syllabus:
        syll_ext = os.path.splitext(syllabus.filename)[1].lower()
        if syll_ext not in ALLOWED_DOCS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported syllabus format '{syllabus.filename}'. Allowed: {', '.join(ALLOWED_DOCS)}"
            )
        syllabus_file_path = os.path.join(upload_path, f"syllabus{syll_ext}")
        with open(syllabus_file_path, "wb") as buffer:
            while True:
                chunk = await syllabus.read(CHUNK_SIZE)
                if not chunk:
                    break
                buffer.write(chunk)
                
    tasks_progress[task_id] = {"status": "Files uploaded. Validating...", "progress": 5}
    
    background_tasks.add_task(
        run_extraction_pipeline,
        task_id=task_id,
        study_file_paths=saved_study_paths,
        syllabus_file_path=syllabus_file_path,
        threshold=threshold,
        math_mode=math_mode,
        handwriting_mode=handwriting_mode
    )
    
    return {"task_id": task_id}

@app.get("/api/process/{task_id}")
@app.get("/process/{task_id}")
async def get_processing_status(task_id: str, request: Request):
    """Server-Sent Events (SSE) progress streaming or JSON status endpoint."""
    if task_id not in tasks_progress:
        raise HTTPException(status_code=404, detail="Task not found.")
        
    accept_header = request.headers.get("accept", "")
    if "text/event-stream" not in accept_header:
        return tasks_progress.get(task_id, {"status": "Initializing...", "progress": 0})
        
    async def status_generator():
        while True:
            progress_data = tasks_progress.get(task_id, {"status": "Initializing...", "progress": 0})
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            if progress_data["progress"] >= 100 or progress_data["progress"] == -1:
                break
                
            await asyncio.sleep(1)
            
    return StreamingResponse(status_generator(), media_type="text/event-stream")

@app.get("/api/results/{task_id}")
@app.get("/results/{task_id}")
async def get_results(task_id: str):
    """Retrieve raw matched results for previewing."""
    if task_id not in tasks_results:
        raise HTTPException(
            status_code=404, 
            detail="Results not found. Task might still be processing or failed."
        )
    return tasks_results[task_id]

@app.post("/api/generate/{task_id}")
@app.post("/generate/{task_id}")
async def generate_output_notes(task_id: str, payload: Dict[str, Any]):
    """
    Generates notes in requested format (DOCX or PDF).
    Payload format: { "topics": [ ... ], "export_format": "docx" | "pdf" }
    """
    if task_id not in tasks_results:
        raise HTTPException(status_code=404, detail="Task results not found.")
        
    customized_topics = payload.get("topics")
    if not customized_topics:
        raise HTTPException(status_code=400, detail="Invalid request. Topics payload is empty.")
        
    export_format = payload.get("export_format", "docx").lower()
    if export_format not in ["docx", "pdf"]:
        export_format = "docx"
        
    _, output_path = get_task_paths(task_id)
    
    try:
        study_name = tasks_results[task_id]["study_file"]
        syllabus_name = tasks_results[task_id]["syllabus_file"]
        title = "Extracted Study Notes"
        desc = f"Organized according to: {syllabus_name}\nSource material: {study_name}"
        
        if export_format == "pdf":
            output_file = os.path.join(output_path, "extracted_notes.pdf")
            generate_pdf(
                matched_results=customized_topics,
                output_path=output_file,
                title=title,
                description=desc
            )
            return {"download_url": f"/api/download/{task_id}?format=pdf", "format": "pdf"}
        else:
            output_file = os.path.join(output_path, "extracted_notes.docx")
            generate_docx(
                matched_results=customized_topics,
                output_path=output_file,
                title=title,
                description=desc
            )
            return {"download_url": f"/api/download/{task_id}?format=docx", "format": "docx"}
            
    except Exception as e:
        logger.error(f"Error generating {export_format}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate {export_format.upper()} document: {str(e)}")

@app.get("/api/download/{task_id}")
@app.get("/download/{task_id}")
async def download_file(task_id: str, format: str = "docx"):
    """Download the generated notes file in requested format (DOCX or PDF)."""
    _, output_path = get_task_paths(task_id)
    fmt = format.lower()
    
    if fmt == "pdf":
        output_file = os.path.join(output_path, "extracted_notes.pdf")
        media_type = "application/pdf"
        filename = "extracted_notes.pdf"
    else:
        output_file = os.path.join(output_path, "extracted_notes.docx")
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "extracted_notes.docx"
        
    if not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail=f"{fmt.upper()} file not found. Generate it first.")
        
    return FileResponse(
        path=output_file,
        media_type=media_type,
        filename=filename
    )

@app.get("/api/health")
@app.get("/health")
async def health_check():
    """Verify if the server is alive."""
    from backend.core.ocr_engine import TESSERACT_AVAILABLE
    return {
        "status": "healthy",
        "tesseract_ocr_available": TESSERACT_AVAILABLE
    }

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
