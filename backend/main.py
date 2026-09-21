# -*- coding: utf-8 -*-
"""
Mento.AI FastAPI Application
Handles multi-file uploads, text syllabus inputs, SSE progress tracking,
preview results with Syllabus Topics & Other Topics selection, and PDF/DOCX format downloads.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
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
    study_files_info: List[Dict[str, str]],
    syllabus_file_path: str,
    syllabus_orig_name: str,
    threshold: float,
    math_mode: bool = False,
    handwriting_mode: bool = False
):
    """
    Background worker pipeline.
    Parses study material files (single or multiple) and syllabus, performs semantic matching,
    detects non-syllabus Other Topics from notes, and compiles the result structure.
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
        total_files = len(study_files_info)
        total_extracted_pages = 0
        total_native_chars = 0
        total_ocr_pages = 0
        
        for idx, item in enumerate(study_files_info):
            file_path = item["path"] if isinstance(item, dict) else item
            orig_name = item.get("filename", os.path.basename(file_path)) if isinstance(item, dict) else os.path.basename(file_path)
            
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
                handwriting_mode=handwriting_mode,
                source_name=orig_name
            )
            all_chunks.extend(chunks)
            
            # Count extraction metrics
            for c in chunks:
                total_extracted_pages = max(total_extracted_pages, c.get("page_number", 1))
                if c.get("type") in ["ocr", "handwriting_ocr"]:
                    total_ocr_pages += 1
                else:
                    total_native_chars += len(c.get("text", ""))
            
        if not all_chunks:
            raise ValueError("No text could be extracted from the uploaded study material(s).")
            
        headings_detected = sum(1 for c in all_chunks if c.get("is_structured_section"))
        logger.info(f"[EXTRACTION] files={total_files} pages={total_extracted_pages} native_text_chars={total_native_chars}")
        if total_ocr_pages > 0:
            logger.info(f"[OCR] pages_processed={total_ocr_pages}")
        logger.info(f"[HEADINGS] detected={headings_detected}")
        logger.info(f"[CHUNKS] total={len(all_chunks)}")
        
        tasks_progress[task_id] = {
            "status": "Initializing AI semantic vector matching...",
            "progress": 70
        }
        
        # 3. Match syllabus to document + Detect Other Topics from study material
        match_data = match_syllabus_to_document(
            topics=topics,
            chunks=all_chunks,
            similarity_threshold=threshold,
            top_k=5
        )
        
        syllabus_matches_count = len([t for t in match_data.get("syllabus_topics", []) if t.get("matches")])
        other_topics_count = len(match_data.get("other_topics", []))
        logger.info(f"[MATCHING] syllabus_matches={syllabus_matches_count}")
        logger.info(f"[OTHER_TOPICS] valid={other_topics_count}")
        
        # Store structured results in-memory and on disk (for cross-instance serverless retrieval)
        study_display_names = [
            (item.get("filename") if isinstance(item, dict) else os.path.basename(item))
            for item in study_files_info
        ]
        results_data = {
            "task_id": task_id,
            "syllabus_topics": match_data.get("syllabus_topics", []),
            "other_topics": match_data.get("other_topics", []),
            "topics": match_data.get("topics", []),
            "chunks": match_data.get("chunks", {}),
            "coverage": match_data.get("coverage", {}),
            "study_file": ", ".join(study_display_names),
            "syllabus_file": syllabus_orig_name,
            "threshold": threshold
        }
        tasks_results[task_id] = results_data
        
        try:
            _, task_output_dir = get_task_paths(task_id)
            results_path = os.path.join(task_output_dir, "results.json")
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(results_data, f, ensure_ascii=False, indent=2)
        except Exception as disk_err:
            logger.warning(f"Could not write results.json to disk for task {task_id}: {disk_err}")
        
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
    Returns a unique task_id. On Vercel, executes synchronously.
    """
    clean_old_files()
    
    if not study_material:
        raise HTTPException(status_code=400, detail="Please upload at least one study material file.")
        
    if not syllabus and not syllabus_text:
        raise HTTPException(status_code=400, detail="Please provide a syllabus file or type syllabus text.")
        
    task_id = generate_task_id()
    upload_path, _ = get_task_paths(task_id)
    
    # Save Study Material files (supports multiple)
    saved_study_info = []
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
        saved_study_info.append({"path": file_path, "filename": s_file.filename})
        
    # Save Syllabus file or text
    syllabus_file_path = os.path.join(upload_path, "syllabus.txt")
    syllabus_orig_name = "Pasted Syllabus Text"
    
    if syllabus_text and syllabus_text.strip():
        with open(syllabus_file_path, "w", encoding="utf-8") as f:
            f.write(syllabus_text.strip())
        syllabus_orig_name = "Pasted Syllabus Text"
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
        syllabus_orig_name = syllabus.filename
                
    tasks_progress[task_id] = {"status": "Files uploaded. Validating...", "progress": 5}
    
    IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
    if IS_VERCEL:
        logger.info(f"Task {task_id}: Running extraction pipeline synchronously on Vercel Serverless...")
        run_extraction_pipeline(
            task_id=task_id,
            study_files_info=saved_study_info,
            syllabus_file_path=syllabus_file_path,
            syllabus_orig_name=syllabus_orig_name,
            threshold=threshold,
            math_mode=math_mode,
            handwriting_mode=handwriting_mode
        )
        res = tasks_results.get(task_id)
        return {"task_id": task_id, "results": res}
    else:
        background_tasks.add_task(
            run_extraction_pipeline,
            task_id=task_id,
            study_files_info=saved_study_info,
            syllabus_file_path=syllabus_file_path,
            syllabus_orig_name=syllabus_orig_name,
            threshold=threshold,
            math_mode=math_mode,
            handwriting_mode=handwriting_mode
        )
        return {"task_id": task_id}

@app.get("/api/process/{task_id}")
@app.get("/process/{task_id}")
@app.get("/api/progress/{task_id}")
@app.get("/progress/{task_id}")
async def get_processing_status(task_id: str, request: Request):
    """Server-Sent Events (SSE) progress streaming or JSON status endpoint."""
    if task_id not in tasks_progress:
        # Check disk if results exist
        _, task_output_dir = get_task_paths(task_id)
        if os.path.exists(os.path.join(task_output_dir, "results.json")):
            return {"status": "Matching completed successfully!", "progress": 100}
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
    """Retrieve matched results and other detected topics for previewing."""
    if task_id in tasks_results:
        return tasks_results[task_id]
        
    # Disk fallback for serverless multi-instance persistence
    _, task_output_dir = get_task_paths(task_id)
    results_path = os.path.join(task_output_dir, "results.json")
    if os.path.exists(results_path):
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                res = json.load(f)
                tasks_results[task_id] = res
                return res
        except Exception as e:
            logger.error(f"Failed to read results.json from disk for task {task_id}: {e}")

    raise HTTPException(
        status_code=404, 
        detail="Results not found. Task might still be processing or failed."
    )

@app.post("/api/generate/{task_id}")
@app.post("/generate/{task_id}")
async def generate_output_notes(task_id: str, payload: Dict[str, Any]):
    """
    Generates notes in requested format (DOCX or PDF).
    Payload format: { "selected_topic_ids": [...], "topics": [ ... ], "export_format": "docx" | "pdf" }
    """
    if task_id not in tasks_results:
        # Try loading from disk
        _, task_output_dir = get_task_paths(task_id)
        results_path = os.path.join(task_output_dir, "results.json")
        if os.path.exists(results_path):
            try:
                with open(results_path, "r", encoding="utf-8") as f:
                    tasks_results[task_id] = json.load(f)
            except Exception:
                pass
                
    if task_id not in tasks_results:
        raise HTTPException(status_code=404, detail="Task results not found.")
        
    task_data = tasks_results[task_id]
    all_stored_topics = task_data.get("topics", [])
    
    selected_topic_ids = payload.get("selected_topic_ids")
    client_custom_topics = payload.get("topics", [])
    export_format = payload.get("export_format", "docx").lower()
    if export_format not in ["docx", "pdf"]:
        export_format = "docx"
        
    final_selected_topics = []
    
    if selected_topic_ids is not None:
        selected_set = set(selected_topic_ids)
        for topic in all_stored_topics:
            if topic.get("topic_id") in selected_set:
                custom_topic = next((ct for ct in client_custom_topics if ct.get("topic_id") == topic["topic_id"]), None)
                if custom_topic and "matches" in custom_topic and len(custom_topic["matches"]) > 0:
                    topic_copy = dict(topic)
                    topic_copy["matches"] = custom_topic["matches"]
                    final_selected_topics.append(topic_copy)
                else:
                    final_selected_topics.append(topic)
    elif client_custom_topics:
        for ct in client_custom_topics:
            if ct.get("matches") and len(ct["matches"]) > 0:
                final_selected_topics.append(ct)
    else:
        final_selected_topics = [t for t in all_stored_topics if t.get("matches")]
        
    # Validate that at least one topic has valid text content
    valid_topics = []
    for t in final_selected_topics:
        valid_matches = []
        for m in t.get("matches", []):
            if m.get("text") and m.get("text").strip():
                valid_matches.append(m)
        if valid_matches:
            t_copy = dict(t)
            t_copy["matches"] = valid_matches
            valid_topics.append(t_copy)
            
    if not valid_topics:
        raise HTTPException(
            status_code=400,
            detail="Some selected topics do not contain extractable source content. Please review the selection and try again."
        )
        
    total_source_chars = sum(len(m.get("text", "")) for t in valid_topics for m in t.get("matches", []))
    logger.info(f"[SELECTION] selected={len(valid_topics)}")
    logger.info(f"[GENERATOR] source_chars={total_source_chars}")
        
    _, output_path = get_task_paths(task_id)
    
    try:
        study_name = task_data.get("study_file", "Study Material")
        syllabus_name = task_data.get("syllabus_file", "Syllabus")
        title = "Extracted Study Notes"
        desc = f"Organized according to: {syllabus_name}\nSource material: {study_name}"
        
        if export_format == "pdf":
            output_file = os.path.join(output_path, "extracted_notes.pdf")
            generate_pdf(
                matched_results=valid_topics,
                output_path=output_file,
                title=title,
                description=desc
            )
            return {"download_url": f"/api/download/{task_id}?format=pdf", "format": "pdf"}
        else:
            output_file = os.path.join(output_path, "extracted_notes.docx")
            generate_docx(
                matched_results=valid_topics,
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
        
    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
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

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the single-page application frontend index.html."""
    for d in ["frontend", "public", "."]:
        index_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d, "index.html")
        if os.path.exists(index_p):
            with open(index_p, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(content="<!DOCTYPE html><html><body><h1>Mento.AI Backend is Running</h1></body></html>")

@app.get("/css/{file_name}")
async def serve_css(file_name: str):
    """Serves CSS styling assets."""
    for d in ["frontend/css", "public/css", "css"]:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d, file_name)
        if os.path.exists(p):
            return FileResponse(p, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS file not found")

@app.get("/js/{file_name}")
async def serve_js(file_name: str):
    """Serves JavaScript application assets."""
    for d in ["frontend/js", "public/js", "js"]:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), d, file_name)
        if os.path.exists(p):
            return FileResponse(p, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JS file not found")

# Serve frontend static files for local development
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(root_dir, "frontend")
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.join(root_dir, "public")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
