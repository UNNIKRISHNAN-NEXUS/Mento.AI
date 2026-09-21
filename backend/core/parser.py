# -*- coding: utf-8 -*-
"""
Mento.AI Document Parser
Parses PDFs (digital & scanned via OCR), DOCX files, TXT files, and Images.
Supports Math Formula Preservation and English Handwriting OCR Recognition.
Splits documents into page-level or block-level chunks for vector embeddings.
"""

import os
import io
import logging
from typing import List, Dict, Any, Callable, Optional
import pymupdf  # PyMuPDF (replaces deprecated 'fitz' import)
from PIL import Image
from docx import Document as DocxDocument
from docx2python import docx2python

from backend.core.ocr_engine import extract_text_from_pixmap, OCR_AVAILABLE
from backend.core.math_parser import format_math_text, is_math_expression
from backend.core.handwriting_ocr import extract_handwritten_text
from backend.core.post_processor import clean_and_normalize_text
from backend.core.heading_detector import segment_into_sections

logger = logging.getLogger("parser")

def clean_text(text: str) -> str:
    """Clean, fix spelling, unwrap line breaks, and normalize extracted text."""
    return clean_and_normalize_text(text)

def parse_pdf(
    file_path: str, 
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    handwriting_mode: bool = False,
    source_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Parse a PDF file page by page into structured sections.
    Strategy:
      - If native text exists (>= 50 alphanumeric characters) and not handwriting mode,
        use high-accuracy PyMuPDF native block extraction (preserves reading order & layout).
      - If page has low digital text density (< 50 chars) or handwriting mode is on,
        render a 200 DPI pixmap and run OCR (RapidOCR / Tesseract).
      - All extracted blocks are routed through `segment_into_sections` to build cohesive
        logical sections where each heading owns all following paragraphs until the next heading.
    """
    raw_blocks = []
    doc_source = source_name or os.path.basename(file_path)
    try:
        doc = pymupdf.open(file_path)
        total_pages = len(doc)
        logger.info(f"Parsing PDF {file_path} with {total_pages} pages. (Math: {math_mode}, Handwriting: {handwriting_mode}, OCR: {OCR_AVAILABLE})")
        
        for i in range(total_pages):
            page = doc[i]
            page_num = i + 1
            
            if progress_callback:
                progress_callback("Extracting PDF Pages", page_num, total_pages)
                
            native_text = page.get_text("text") or ""
            alpha_chars = sum(1 for c in native_text if c.isalnum())
            
            # Check whether real text exists (>= 50 alphanumeric characters)
            if not handwriting_mode and alpha_chars >= 50:
                chunk_type = "digital"
                page_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
                for b in page_blocks:
                    if len(b) >= 7 and b[6] != 0:
                        continue  # skip image blocks
                    b_text = b[4].strip() if len(b) >= 5 else ""
                    if not b_text:
                        continue
                    cleaned = clean_text(b_text)
                    if math_mode or is_math_expression(cleaned):
                        cleaned = format_math_text(cleaned)
                    if cleaned:
                        raw_blocks.append({
                            "text": cleaned,
                            "page_number": page_num,
                            "type": chunk_type
                        })
            elif OCR_AVAILABLE:
                logger.info(f"Page {page_num}: Running OCR pipeline (alpha_chars={alpha_chars}, handwriting={handwriting_mode})...")
                if progress_callback:
                    progress_callback(f"Running OCR on Page {page_num}", page_num, total_pages)
                
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes))
                
                if handwriting_mode:
                    ocr_text = extract_handwritten_text(pil_img)
                    chunk_type = "handwriting_ocr"
                else:
                    ocr_text = extract_text_from_pixmap(pix)
                    chunk_type = "ocr"
                    
                cleaned = clean_text(ocr_text)
                if math_mode or is_math_expression(cleaned):
                    cleaned = format_math_text(cleaned)
                if cleaned:
                    raw_blocks.append({
                        "text": cleaned,
                        "page_number": page_num,
                        "type": chunk_type
                    })
            else:
                cleaned = clean_text(native_text)
                if cleaned:
                    raw_blocks.append({
                        "text": cleaned,
                        "page_number": page_num,
                        "type": "digital"
                    })
        
        doc.close()
        
        # Segment raw extracted blocks into coherent sections anchored by academic headings
        chunks = segment_into_sections(raw_blocks, doc_source)
        logger.info(f"PDF {file_path} parsed into {len(chunks)} structured section chunks.")
        return chunks
        
    except Exception as e:
        logger.error(f"Error parsing PDF file {file_path}: {e}")
        raise e

def parse_docx(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    source_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse a DOCX file into structured sections anchored by headings."""
    doc_source = source_name or os.path.basename(file_path)
    try:
        logger.info(f"Parsing DOCX {file_path}")
        if progress_callback:
            progress_callback("Reading DOCX File Structure", 1, 3)
            
        try:
            with docx2python(file_path) as docx_content:
                text_content = docx_content.text
            paragraphs = [p.strip() for p in text_content.split("\n\n") if p.strip()]
        except Exception as e:
            logger.warning(f"docx2python fallback to python-docx: {e}")
            doc = DocxDocument(file_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            
        if progress_callback:
            progress_callback("Structuring DOCX Paragraphs", 2, 3)
            
        raw_blocks = []
        for p_idx, p in enumerate(paragraphs):
            para_text = clean_text(p)
            if math_mode or is_math_expression(para_text):
                para_text = format_math_text(para_text)
            if para_text:
                raw_blocks.append({
                    "text": para_text,
                    "page_number": (p_idx // 15) + 1,
                    "type": "digital"
                })
                
        chunks = segment_into_sections(raw_blocks, doc_source)
        if progress_callback:
            progress_callback("DOCX Parsing Completed", 3, 3)
            
        logger.info(f"DOCX {file_path} parsed into {len(chunks)} structured section chunks.")
        return chunks
        
    except Exception as e:
        logger.error(f"Error parsing DOCX file {file_path}: {e}")
        raise e

def parse_txt(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    source_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse plain text files into structured sections."""
    doc_source = source_name or os.path.basename(file_path)
    try:
        logger.info(f"Parsing TXT {file_path}")
        if progress_callback:
            progress_callback("Reading TXT File", 1, 2)
            
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        raw_blocks = []
        for idx, line in enumerate(lines):
            cleaned = clean_text(line)
            if math_mode or is_math_expression(cleaned):
                cleaned = format_math_text(cleaned)
            if cleaned:
                raw_blocks.append({
                    "text": cleaned,
                    "page_number": (idx // 40) + 1,
                    "type": "digital"
                })
                
        chunks = segment_into_sections(raw_blocks, doc_source)
        if progress_callback:
            progress_callback("TXT Parsing Completed", 2, 2)
            
        logger.info(f"TXT {file_path} parsed into {len(chunks)} structured section chunks.")
        return chunks
        
    except Exception as e:
        logger.error(f"Error parsing TXT file {file_path}: {e}")
        raise e

def parse_image(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    handwriting_mode: bool = False,
    source_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse image file (PNG, JPG, JPEG, WEBP) using OCR or Handwriting Engine into structured sections."""
    from backend.core.ocr_engine import extract_text_from_image
    doc_source = source_name or os.path.basename(file_path)
    try:
        logger.info(f"Parsing Image {file_path} (Handwriting: {handwriting_mode}, Math: {math_mode})")
        if progress_callback:
            progress_callback("Running OCR/Handwriting Engine", 1, 1)
            
        image = Image.open(file_path)
        
        if handwriting_mode:
            ocr_text = extract_handwritten_text(image)
            chunk_type = "handwriting_ocr"
        else:
            ocr_text = extract_text_from_image(image)
            chunk_type = "ocr"
            
        cleaned_text = clean_text(ocr_text)
        if math_mode or is_math_expression(cleaned_text):
            cleaned_text = format_math_text(cleaned_text)
            
        raw_blocks = [{"text": cleaned_text, "page_number": 1, "type": chunk_type}]
        chunks = segment_into_sections(raw_blocks, doc_source)
        return chunks
        
    except Exception as e:
        logger.error(f"Error parsing image file {file_path}: {e}")
        raise e

def parse_document(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    handwriting_mode: bool = False,
    source_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Main document parsing router."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(file_path, progress_callback, math_mode, handwriting_mode, source_name=source_name)
    elif ext == ".docx":
        return parse_docx(file_path, progress_callback, math_mode, source_name=source_name)
    elif ext in [".txt", ".md"]:
        return parse_txt(file_path, progress_callback, math_mode, source_name=source_name)
    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        return parse_image(file_path, progress_callback, math_mode, handwriting_mode, source_name=source_name)
    else:
        raise ValueError(f"Unsupported file format '{ext}'")
