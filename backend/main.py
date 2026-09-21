# -*- coding: utf-8 -*-
"""
Mento.AI FastAPI Application
Handles multi-file uploads, text syllabus inputs, SSE progress tracking,
preview results with Syllabus Topics & Other Topics selection, PDF/DOCX format downloads,
and diagnostic inspection endpoints.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.utils.file_utils import (
    generate_task_id, get_task_paths, clean_old_files, validate_file_extension
)
from backend.core.parser import parse_document
from backend.core.syllabus_parser import parse_syllabus
from backend.core.matcher import match_syllabus_to_document, compute_coverage_audit
from backend.core.docx_generator import generate_docx, generate_pdf, validate_generated_document

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="Mento.AI", description="AI-Powered Syllabus-Based Notes Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks_progress: Dict[str, Dict[str, Any]] = {}
tasks_results: Dict[str, Dict[str, Any]] = {}
tasks_diagnostics: Dict[str, Dict[str, Any]] = {}

ALLOWED_DOCS = {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}

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
    Parses syllabus and study material documents into separate structured objects,
    performs semantic matching, groups non-syllabus material, and logs complete diagnostic metrics.
    """
    try:
        tasks_progress[task_id] = {"status": "Parsing syllabus...", "progress": 10}
        logger.info(f"Task {task_id}: Parsing syllabus...")
        
        # 1. Parse syllabus (INDEX ONLY)
        syllabus_topics = parse_syllabus(syllabus_file_path)
        if not syllabus_topics:
            raise ValueError("No topics could be extracted from the syllabus.")
            
        syllabus_chars = 0
        if os.path.exists(syllabus_file_path):
            with open(syllabus_file_path, "r", encoding="utf-8", errors="ignore") as sf:
                syllabus_chars = len(sf.read())
                
        tasks_progress[task_id] = {
            "status": f"Syllabus parsed: Found {len(syllabus_topics)} topics. Parsing study materials...", 
            "progress": 25
        }
        
        # 2. Parse study materials (CONTENT SOURCE)
        all_chunks = []
        total_files = len(study_files_info)
        total_extracted_pages = 0
        total_native_chars = 0
        total_native_pages = 0
        total_ocr_pages = 0
        total_handwriting_pages = 0
        total_tables = 0
        
        task_upload_dir, _ = get_task_paths(task_id)
        task_image_dir = os.path.join(task_upload_dir, "images")
        os.makedirs(task_image_dir, exist_ok=True)
        
        for idx, item in enumerate(study_files_info):
            file_path = item["path"] if isinstance(item, dict) else item
            orig_name = item.get("filename", os.path.basename(file_path)) if isinstance(item, dict) else os.path.basename(file_path)
            
            def parser_progress(stage: str, current: int, total: int):
                step_pct = 25 + int(((idx + (current / max(total, 1))) / total_files) * 40)
                tasks_progress[task_id] = {
                    "status": f"[{idx+1}/{total_files}] {stage}...",
                    "progress": step_pct
                }
                
            chunks = parse_document(
                file_path, 
                progress_callback=parser_progress,
                math_mode=math_mode,
                handwriting_mode=handwriting_mode,
                source_name=orig_name,
                image_dir=task_image_dir
            )
            all_chunks.extend(chunks)
            
            for c in chunks:
                total_extracted_pages = max(total_extracted_pages, c.get("page_number", 1))
                c_type = c.get("type", "digital")
                if c_type == "handwriting_ocr":
                    total_handwriting_pages += 1
                elif c_type == "ocr":
                    total_ocr_pages += 1
                else:
                    total_native_pages += 1
                    total_native_chars += len(c.get("text", ""))
                total_tables += len(c.get("tables", []))
            
        if not all_chunks:
            raise ValueError("No text could be extracted from the uploaded study material(s).")
            
        headings_detected = sum(1 for c in all_chunks if c.get("is_structured_section"))
        total_extracted_images = sum(len(c.get("images", [])) for c in all_chunks)
        total_source_chars = sum(len(c.get("text", "")) for c in all_chunks)
        
        # EXACT REQUIRED DIAGNOSTIC LOG
        study_display_names = [
            (item.get("filename") if isinstance(item, dict) else os.path.basename(item))
            for item in study_files_info
        ]
        
        print("\n" + "=" * 45)
        print("========== DOCUMENT INGESTION ==========")
        print(f"SYLLABUS:")
        print(f"  filename: {syllabus_orig_name}")
        print(f"  characters: {syllabus_chars}")
        print(f"  topics detected: {len(syllabus_topics)}")
        print(f"\nSTUDY MATERIAL:")
        print(f"  filename: {', '.join(study_display_names)}")
        print(f"  pages: {total_extracted_pages}")
        print(f"  characters: {total_source_chars}")
        print(f"  headings: {headings_detected}")
        print(f"  paragraphs: {len(all_chunks)}")
        print(f"  images: {total_extracted_images}")
        print(f"  tables: {total_tables}")
        print("=" * 45 + "\n")
        
        tasks_progress[task_id] = {
            "status": "Matching syllabus to study material notes...",
            "progress": 70
        }
        
        # 3. Match syllabus to document + Detect Other Topics + Retain 100% of material
        match_data = match_syllabus_to_document(
            topics=syllabus_topics,
            chunks=all_chunks,
            similarity_threshold=threshold,
            top_k=25
        )
        
        print("\n" + "=" * 45)
        print("========== MATCHING ==========")
        for t in match_data.get("syllabus_topics", []):
            t_name = t.get("title", "Unknown")
            p_list = t.get("source_pages", [])
            chars_cnt = t.get("source_text_chars", 0)
            pages_str = ",".join(str(p) for p in p_list) if p_list else "None"
            print(f"Topic: {t_name}")
            print(f"  Matched source pages: {pages_str}")
            print(f"  Matched text characters: {chars_cnt}")
        print("=" * 45 + "\n")
        
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
        
        # Store diagnostics
        tasks_diagnostics[task_id] = {
            "source_pages": total_extracted_pages,
            "processed_pages": total_extracted_pages,
            "failed_pages": [],
            "native_text_pages": total_native_pages,
            "ocr_pages": total_ocr_pages,
            "handwriting_pages": total_handwriting_pages,
            "detected_topics": len(match_data.get("topics", [])),
            "selected_topics": len(match_data.get("topics", [])),
            "source_text_chars": total_source_chars,
            "images_extracted": total_extracted_images,
            "output_pages": 0,
            "output_text_chars": 0,
            "images_rendered": 0
        }
        
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
    threshold: float = Form(0.25),
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
                # If client passed specific custom excerpts for this topic, use them if non-empty
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
        
    # Validate that topics contain content
    valid_topics = []
    for t in final_selected_topics:
        valid_matches = []
        for m in t.get("matches", []):
            has_text = bool(m.get("text") and m.get("text").strip())
            has_images = bool(m.get("images") and len(m["images"]) > 0)
            has_tables = bool(m.get("tables") and len(m["tables"]) > 0)
            if has_text or has_images or has_tables:
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
    total_source_images = sum(len(m.get("images", [])) for t in valid_topics for m in t.get("matches", []))
    total_source_tables = sum(len(m.get("tables", [])) for t in valid_topics for m in t.get("matches", []))
    all_pages = sorted(set(m.get("page_number", 1) for t in valid_topics for m in t.get("matches", [])))
    
    # EXACT REQUIRED DIAGNOSTIC LOG
    print("\n" + "=" * 45)
    print("========== GENERATION INPUT ==========")
    print(f"Topics selected: {len(valid_topics)}\n")
    for idx, t in enumerate(valid_topics):
        t_pages = sorted(set(m.get("page_number", 1) for m in t.get("matches", [])))
        t_chars = sum(len(m.get("text", "")) for m in t.get("matches", []))
        t_imgs = sum(len(m.get("images", [])) for m in t.get("matches", []))
        print(f"Topic {idx+1}:")
        print(f"  Name: {t.get('title')}")
        print(f"  Source pages: {','.join(str(p) for p in t_pages)}")
        print(f"  Text characters: {t_chars}")
        print(f"  Images: {t_imgs}\n")
    print(f"TOTAL SOURCE TEXT: {total_source_chars} characters")
    print(f"TOTAL SOURCE PAGES: {len(all_pages)}")
    print("=" * 45 + "\n")
        
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
            val_rep = validate_generated_document(output_file, export_format="pdf")
            
            # Post-generation validation failure check
            if val_rep.get("total_chars", 0) < 50 and val_rep.get("images_count", 0) == 0:
                raise ValueError("Generated PDF is empty or missing study content.")
                
            if len(all_pages) >= 5 and val_rep.get("page_count", 1) == 1:
                raise ValueError(f"Generation anomaly: {len(all_pages)} source pages collapsed into 1 output page.")
                
            if task_id in tasks_diagnostics:
                tasks_diagnostics[task_id]["output_pages"] = val_rep.get("page_count", 1)
                tasks_diagnostics[task_id]["output_text_chars"] = val_rep.get("total_chars", 0)
                tasks_diagnostics[task_id]["images_rendered"] = val_rep.get("images_count", 0)
                tasks_diagnostics[task_id]["selected_topics"] = len(valid_topics)
                
            print(f"[VALIDATION] Output pages: {val_rep.get('page_count', 1)} | Output chars: {val_rep.get('total_chars', 0)} | Status: PASS\n")
            return {"download_url": f"/api/download/{task_id}?format=pdf", "format": "pdf"}
        else:
            output_file = os.path.join(output_path, "extracted_notes.docx")
            generate_docx(
                matched_results=valid_topics,
                output_path=output_file,
                title=title,
                description=desc
            )
            val_rep = validate_generated_document(output_file, export_format="docx")
            
            if val_rep.get("total_chars", 0) < 50 and val_rep.get("images_count", 0) == 0:
                raise ValueError("Generated DOCX is empty or missing study content.")
                
            if task_id in tasks_diagnostics:
                tasks_diagnostics[task_id]["output_pages"] = 1
                tasks_diagnostics[task_id]["output_text_chars"] = val_rep.get("total_chars", 0)
                tasks_diagnostics[task_id]["images_rendered"] = val_rep.get("images_count", 0)
                tasks_diagnostics[task_id]["selected_topics"] = len(valid_topics)
                
            print(f"[VALIDATION] Output DOCX chars: {val_rep.get('total_chars', 0)} | Status: PASS\n")
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

@app.get("/api/debug/{task_id}")
@app.get("/debug/{task_id}")
async def get_task_diagnostics(task_id: str):
    """
    Diagnostic endpoint returning end-to-end processing and validation metrics.
    """
    if task_id in tasks_diagnostics:
        return tasks_diagnostics[task_id]
        
    if task_id in tasks_results:
        res = tasks_results[task_id]
        topics = res.get("topics", [])
        total_chars = sum(len(m.get("text", "")) for t in topics for m in t.get("matches", []))
        total_imgs = sum(len(m.get("images", [])) for t in topics for m in t.get("matches", []))
        return {
            "task_id": task_id,
            "detected_topics": len(topics),
            "source_text_chars": total_chars,
            "images_extracted": total_imgs,
            "status": "completed"
        }
        
    raise HTTPException(status_code=404, detail="Task diagnostic information not found.")

@app.get("/api/health")
@app.get("/health")
async def health_check():
    """Verify if the server is alive and report OCR capabilities."""
    from backend.core.ocr_engine import RAPIDOCR_AVAILABLE, TESSERACT_AVAILABLE
    return {
        "status": "healthy",
        "rapidocr_available": RAPIDOCR_AVAILABLE,
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

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(root_dir, "frontend")
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.join(root_dir, "public")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
