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

from backend.core.ocr_engine import extract_text_from_pixmap, TESSERACT_AVAILABLE
from backend.core.math_parser import format_math_text, is_math_expression
from backend.core.handwriting_ocr import extract_handwritten_text

logger = logging.getLogger("parser")

def clean_text(text: str) -> str:
    """Clean extra spaces and redundant newlines from text."""
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)

def parse_pdf(
    file_path: str, 
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    handwriting_mode: bool = False
) -> List[Dict[str, Any]]:
    """
    Parse a PDF file page by page.
    Uses direct text extraction, math symbol normalization, and handwriting OCR.
    """
    chunks = []
    try:
        doc = pymupdf.open(file_path)
        total_pages = len(doc)
        logger.info(f"Parsing PDF {file_path} with {total_pages} pages. (Math: {math_mode}, Handwriting: {handwriting_mode})")
        
        for i in range(total_pages):
            page = doc[i]
            page_num = i + 1
            
            if progress_callback:
                progress_callback("Extracting PDF Pages", page_num, total_pages)
                
            text = page.get_text("text")
            cleaned_text = clean_text(text)
            
            # Check if handwriting OCR is requested or page has low digital text density
            if handwriting_mode or (len(cleaned_text) < 100 and TESSERACT_AVAILABLE):
                logger.info(f"Page {page_num}: Running Handwriting/OCR pipeline...")
                if progress_callback:
                    progress_callback(f"Running OCR on Page {page_num}", page_num, total_pages)
                
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes))
                
                if handwriting_mode:
                    ocr_text = extract_handwritten_text(pil_img)
                else:
                    ocr_text = extract_text_from_pixmap(pix)
                    
                cleaned_text = clean_text(ocr_text)
                chunk_type = "handwriting_ocr" if handwriting_mode else "ocr"
            else:
                chunk_type = "digital"
                
            # Apply Math Formula normalization if math_mode is enabled
            if math_mode or is_math_expression(cleaned_text):
                cleaned_text = format_math_text(cleaned_text)
                
            if cleaned_text:
                chunks.append({
                    "chunk_id": f"page_{page_num}",
                    "text": cleaned_text,
                    "page_number": page_num,
                    "type": chunk_type,
                    "source": os.path.basename(file_path)
                })
        
        doc.close()
    except Exception as e:
        logger.error(f"Error parsing PDF file {file_path}: {e}")
        raise e
        
    return chunks

def parse_docx(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False
) -> List[Dict[str, Any]]:
    """Parse a DOCX file into paragraph blocks with optional math normalization."""
    chunks = []
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
            progress_callback("Chunking DOCX Paragraphs", 2, 3)
            
        current_chunk = []
        current_len = 0
        chunk_idx = 1
        
        for p in paragraphs:
            para_text = format_math_text(p) if (math_mode or is_math_expression(p)) else p
            current_chunk.append(para_text)
            current_len += len(para_text)
            
            if current_len >= 1200:
                chunks.append({
                    "chunk_id": f"block_{chunk_idx}",
                    "text": "\n\n".join(current_chunk),
                    "page_number": (chunk_idx // 3) + 1,
                    "type": "digital",
                    "source": os.path.basename(file_path)
                })
                current_chunk = []
                current_len = 0
                chunk_idx += 1
                
        if current_chunk:
            chunks.append({
                "chunk_id": f"block_{chunk_idx}",
                "text": "\n\n".join(current_chunk),
                "page_number": (chunk_idx // 3) + 1,
                "type": "digital",
                "source": os.path.basename(file_path)
            })
            
        if progress_callback:
            progress_callback("DOCX Parsing Completed", 3, 3)
            
    except Exception as e:
        logger.error(f"Error parsing DOCX file {file_path}: {e}")
        raise e
        
    return chunks

def parse_txt(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False
) -> List[Dict[str, Any]]:
    """Parse plain text files into chunks."""
    chunks = []
    try:
        logger.info(f"Parsing TXT {file_path}")
        if progress_callback:
            progress_callback("Reading TXT File", 1, 2)
            
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        current_chunk = []
        current_len = 0
        chunk_idx = 1
        
        for p in paragraphs:
            para_text = format_math_text(p) if (math_mode or is_math_expression(p)) else p
            current_chunk.append(para_text)
            current_len += len(para_text)
            
            if current_len >= 1200:
                chunks.append({
                    "chunk_id": f"block_{chunk_idx}",
                    "text": "\n\n".join(current_chunk),
                    "page_number": (chunk_idx // 3) + 1,
                    "type": "digital",
                    "source": os.path.basename(file_path)
                })
                current_chunk = []
                current_len = 0
                chunk_idx += 1
                
        if current_chunk:
            chunks.append({
                "chunk_id": f"block_{chunk_idx}",
                "text": "\n\n".join(current_chunk),
                "page_number": (chunk_idx // 3) + 1,
                "type": "digital",
                "source": os.path.basename(file_path)
            })
            
        if progress_callback:
            progress_callback("TXT Parsing Completed", 2, 2)
            
    except Exception as e:
        logger.error(f"Error parsing TXT file {file_path}: {e}")
        raise e
        
    return chunks

def parse_image(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    handwriting_mode: bool = False
) -> List[Dict[str, Any]]:
    """Parse image file (PNG, JPG, JPEG, WEBP) using OCR or Handwriting Engine."""
    from backend.core.ocr_engine import extract_text_from_image
    chunks = []
    try:
        logger.info(f"Parsing Image {file_path} (Handwriting: {handwriting_mode}, Math: {math_mode})")
        if progress_callback:
            progress_callback("Running OCR/Handwriting Engine", 1, 1)
            
        image = Image.open(file_path)
        
        if handwriting_mode:
            ocr_text = extract_handwritten_text(image)
        else:
            ocr_text = extract_text_from_image(image)
            
        cleaned_text = clean_text(ocr_text)
        
        if math_mode or is_math_expression(cleaned_text):
            cleaned_text = format_math_text(cleaned_text)
            
        if cleaned_text:
            chunks.append({
                "chunk_id": "image_1",
                "text": cleaned_text,
                "page_number": 1,
                "type": "handwriting_ocr" if handwriting_mode else "ocr",
                "source": os.path.basename(file_path)
            })
    except Exception as e:
        logger.error(f"Error parsing image file {file_path}: {e}")
        raise e
        
    return chunks

def parse_document(
    file_path: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    handwriting_mode: bool = False
) -> List[Dict[str, Any]]:
    """Main document parsing router."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(file_path, progress_callback, math_mode, handwriting_mode)
    elif ext == ".docx":
        return parse_docx(file_path, progress_callback, math_mode)
    elif ext in [".txt", ".md"]:
        return parse_txt(file_path, progress_callback, math_mode)
    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        return parse_image(file_path, progress_callback, math_mode, handwriting_mode)
    else:
        raise ValueError(f"Unsupported file format '{ext}'")
