# -*- coding: utf-8 -*-
"""
Mento.AI Document Parser
Parses PDFs (digital & scanned via OCR), DOCX files, TXT files, and Images.
Extracts embedded images, diagrams, figures, and charts with positional metadata.
Supports Math Formula Preservation and English Handwriting OCR Recognition.
Segments documents into structure-aware sections anchored by academic headings.
"""

import os
import io
import re
import hashlib
import logging
from typing import List, Dict, Any, Callable, Optional, Set, Tuple
import pymupdf  # PyMuPDF
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

def _slugify(name: str) -> str:
    """Sanitize filename into a clean slug."""
    s = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    return re.sub(r'_+', '_', s).strip('_')

def extract_images_from_pdf(
    file_path: str,
    image_dir: Optional[str] = None,
    source_name: Optional[str] = None
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Extracts embedded raster images and diagrams from a PDF.
    Returns a dictionary mapping page_number (1-based) -> list of image descriptor dicts.
    Filters out small icons, bullets, and deduplicates repeated images (e.g. logos).
    """
    images_by_page: Dict[int, List[Dict[str, Any]]] = {}
    if not image_dir:
        return images_by_page
        
    os.makedirs(image_dir, exist_ok=True)
    doc_source = source_name or os.path.basename(file_path)
    source_slug = _slugify(doc_source)
    seen_hashes: Set[str] = set()
    
    try:
        doc = pymupdf.open(file_path)
        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            page = doc[page_idx]
            page_images: List[Dict[str, Any]] = []
            
            image_list = page.get_images(full=True)
            page_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
            
            for img_idx, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue
                        
                    image_bytes = base_image.get("image")
                    if not image_bytes:
                        continue
                        
                    image_ext = base_image.get("ext", "png").lower()
                    if image_ext not in ["png", "jpg", "jpeg", "webp"]:
                        image_ext = "png"
                        
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)
                    
                    # Filter out tiny icons, decorative bullets, separator bars
                    if width < 45 or height < 45 or (width * height) < 2500:
                        continue
                        
                    # Deduplicate identical images across document (e.g. headers/watermarks)
                    img_hash = hashlib.md5(image_bytes).hexdigest()
                    if img_hash in seen_hashes:
                        continue
                    seen_hashes.add(img_hash)
                    
                    # Get bounding box on page
                    rects = page.get_image_rects(xref)
                    bbox = [round(v, 1) for v in rects[0]] if rects else [0, 0, width, height]
                    
                    # Look for nearby caption in surrounding text blocks
                    caption = ""
                    if rects and page_blocks:
                        img_rect = rects[0]
                        for b in page_blocks:
                            if len(b) >= 5:
                                bx0, by0, bx1, by1, btext = b[0], b[1], b[2], b[3], b[4].strip()
                                # Text block located right below or above the image (within 55pt)
                                is_below = (0 <= (by0 - img_rect.y1) <= 55)
                                is_above = (0 <= (img_rect.y0 - by1) <= 45)
                                if is_below or is_above:
                                    first_line = btext.splitlines()[0].strip() if btext else ""
                                    if re.match(r'^(fig|figure|diagram|table|graph|chart|circuit|model)\b', first_line, re.I):
                                        caption = first_line[:120]
                                        break
                                    elif len(first_line) < 75 and is_below:
                                        caption = first_line
                    
                    # Save image file
                    img_filename = f"{source_slug}_p{page_num}_img{img_idx+1}.{image_ext}"
                    img_path = os.path.join(image_dir, img_filename)
                    with open(img_path, "wb") as f:
                        f.write(image_bytes)
                        
                    img_desc = {
                        "image_id": f"{source_slug}_p{page_num}_img{img_idx+1}",
                        "source": doc_source,
                        "page_number": page_num,
                        "bbox": bbox,
                        "width": width,
                        "height": height,
                        "path": img_path,
                        "caption": caption,
                        "aspect_ratio": round(width / max(height, 1), 3)
                    }
                    page_images.append(img_desc)
                except Exception as img_err:
                    logger.debug(f"Error extracting image {img_idx} on page {page_num}: {img_err}")
                    
            if page_images:
                images_by_page[page_num] = page_images
                
        doc.close()
    except Exception as e:
        logger.warning(f"Failed to extract images from PDF {file_path}: {e}")
        
    return images_by_page

def extract_images_from_docx(
    file_path: str,
    image_dir: Optional[str] = None,
    source_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extracts embedded images from a DOCX document using docx2python or python-docx.
    Returns a list of image descriptor dicts.
    """
    extracted_images: List[Dict[str, Any]] = []
    if not image_dir:
        return extracted_images
        
    os.makedirs(image_dir, exist_ok=True)
    doc_source = source_name or os.path.basename(file_path)
    source_slug = _slugify(doc_source)
    seen_hashes: Set[str] = set()
    img_idx = 1
    
    # 1. Try docx2python media extraction
    try:
        with docx2python(file_path) as doc_content:
            images_dict = getattr(doc_content, "images", {})
            if images_dict:
                for img_name, img_bytes in images_dict.items():
                    if not img_bytes:
                        continue
                    img_hash = hashlib.md5(img_bytes).hexdigest()
                    if img_hash in seen_hashes:
                        continue
                    seen_hashes.add(img_hash)
                    
                    try:
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        w, h = pil_img.size
                        if w < 45 or h < 45 or (w * h) < 2500:
                            continue
                    except Exception:
                        w, h = 400, 300
                        
                    ext = os.path.splitext(img_name)[1].lstrip('.').lower() or "png"
                    if ext not in ["png", "jpg", "jpeg", "webp"]:
                        ext = "png"
                        
                    img_filename = f"{source_slug}_img{img_idx}.{ext}"
                    img_path = os.path.join(image_dir, img_filename)
                    with open(img_path, "wb") as f:
                        f.write(img_bytes)
                        
                    extracted_images.append({
                        "image_id": f"{source_slug}_img{img_idx}",
                        "source": doc_source,
                        "page_number": 1,
                        "width": w,
                        "height": h,
                        "path": img_path,
                        "caption": "",
                        "aspect_ratio": round(w / max(h, 1), 3)
                    })
                    img_idx += 1
    except Exception as e:
        logger.debug(f"docx2python image extraction fallback: {e}")
        
    # 2. Fallback to python-docx part relationships if none found
    if not extracted_images:
        try:
            doc = DocxDocument(file_path)
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        img_bytes = rel.target_part.blob
                        img_hash = hashlib.md5(img_bytes).hexdigest()
                        if img_hash in seen_hashes:
                            continue
                        seen_hashes.add(img_hash)
                        
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        w, h = pil_img.size
                        if w < 45 or h < 45 or (w * h) < 2500:
                            continue
                            
                        ext = "png"
                        if hasattr(pil_img, "format") and pil_img.format:
                            ext = pil_img.format.lower()
                            if ext == "jpeg":
                                ext = "jpg"
                                
                        img_filename = f"{source_slug}_img{img_idx}.{ext}"
                        img_path = os.path.join(image_dir, img_filename)
                        with open(img_path, "wb") as f:
                            f.write(img_bytes)
                            
                        extracted_images.append({
                            "image_id": f"{source_slug}_img{img_idx}",
                            "source": doc_source,
                            "page_number": 1,
                            "width": w,
                            "height": h,
                            "path": img_path,
                            "caption": "",
                            "aspect_ratio": round(w / max(h, 1), 3)
                        })
                        img_idx += 1
                    except Exception as part_err:
                        logger.debug(f"Error extracting python-docx image rel: {part_err}")
        except Exception as docx_err:
            logger.warning(f"Failed to extract images from DOCX {file_path}: {docx_err}")
            
    return extracted_images

def parse_pdf(
    file_path: str, 
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    math_mode: bool = False,
    handwriting_mode: bool = False,
    source_name: Optional[str] = None,
    image_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Parse a PDF file into structured sections.
    Extracts text, formulas, diagrams, and figures.
    Associates images to their corresponding section chunks.
    """
    raw_blocks = []
    doc_source = source_name or os.path.basename(file_path)
    
    # 1. Extract images per page
    pdf_images_by_page = extract_images_from_pdf(file_path, image_dir=image_dir, source_name=doc_source)
    total_extracted_imgs = sum(len(imgs) for imgs in pdf_images_by_page.values())
    if total_extracted_imgs > 0:
        logger.info(f"Extracted {total_extracted_imgs} embedded images/diagrams from PDF {file_path}")
        
    try:
        doc = pymupdf.open(file_path)
        total_pages = len(doc)
        logger.info(f"Parsing PDF {file_path} ({total_pages} pages). (Math: {math_mode}, Handwriting: {handwriting_mode}, OCR: {OCR_AVAILABLE})")
        
        for i in range(total_pages):
            page = doc[i]
            page_num = i + 1
            page_images = pdf_images_by_page.get(page_num, [])
            
            if progress_callback:
                progress_callback("Extracting PDF Content", page_num, total_pages)
                
            native_text = page.get_text("text") or ""
            alpha_chars = sum(1 for c in native_text if c.isalnum())
            
            # Check whether digital text exists (>= 50 alphanumeric characters)
            if not handwriting_mode and alpha_chars >= 50:
                chunk_type = "digital"
                page_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
                
                # Filter text blocks
                text_blocks = [b for b in page_blocks if len(b) >= 5 and (len(b) < 7 or b[6] == 0) and b[4].strip()]
                
                for b_idx, b in enumerate(text_blocks):
                    b_text = b[4].strip()
                    cleaned = clean_text(b_text)
                    if math_mode or is_math_expression(cleaned):
                        cleaned = format_math_text(cleaned)
                    if cleaned:
                        # Attach page images to the last block of the page
                        block_imgs = page_images if b_idx == len(text_blocks) - 1 else []
                        raw_blocks.append({
                            "text": cleaned,
                            "page_number": page_num,
                            "type": chunk_type,
                            "images": block_imgs
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
                    
                # If no embedded images were found on this scanned page, save the rendered page pixmap as an image
                if not page_images and image_dir and (len(cleaned) > 20 or handwriting_mode):
                    try:
                        scanned_img_name = f"{_slugify(doc_source)}_p{page_num}_scan.png"
                        scanned_img_path = os.path.join(image_dir, scanned_img_name)
                        pix.save(scanned_img_path)
                        page_images = [{
                            "image_id": f"{_slugify(doc_source)}_p{page_num}_scan",
                            "source": doc_source,
                            "page_number": page_num,
                            "bbox": [0, 0, pix.width, pix.height],
                            "width": pix.width,
                            "height": pix.height,
                            "path": scanned_img_path,
                            "caption": f"Page {page_num} Diagram/Notes",
                            "aspect_ratio": round(pix.width / max(pix.height, 1), 3)
                        }]
                    except Exception as scan_err:
                        logger.debug(f"Could not save scanned page image: {scan_err}")
                        
                if cleaned:
                    raw_blocks.append({
                        "text": cleaned,
                        "page_number": page_num,
                        "type": chunk_type,
                        "images": page_images
                    })
            else:
                cleaned = clean_text(native_text)
                if cleaned:
                    raw_blocks.append({
                        "text": cleaned,
                        "page_number": page_num,
                        "type": "digital",
                        "images": page_images
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
    source_name: Optional[str] = None,
    image_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse a DOCX file into structured sections anchored by headings, including extracted images."""
    doc_source = source_name or os.path.basename(file_path)
    try:
        logger.info(f"Parsing DOCX {file_path}")
        if progress_callback:
            progress_callback("Reading DOCX File Structure", 1, 3)
            
        docx_images = extract_images_from_docx(file_path, image_dir=image_dir, source_name=doc_source)
        if docx_images:
            logger.info(f"Extracted {len(docx_images)} images from DOCX {file_path}")
            
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
        total_p = len(paragraphs)
        for p_idx, p in enumerate(paragraphs):
            para_text = clean_text(p)
            if math_mode or is_math_expression(para_text):
                para_text = format_math_text(para_text)
            if para_text:
                # Distribute docx images evenly across blocks or on the last block
                block_imgs = docx_images if (p_idx == total_p - 1 and docx_images) else []
                raw_blocks.append({
                    "text": para_text,
                    "page_number": (p_idx // 15) + 1,
                    "type": "digital",
                    "images": block_imgs
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
    source_name: Optional[str] = None,
    image_dir: Optional[str] = None
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
                    "type": "digital",
                    "images": []
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
    source_name: Optional[str] = None,
    image_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse image file (PNG, JPG, JPEG, WEBP) using OCR or Handwriting Engine into structured sections."""
    from backend.core.ocr_engine import extract_text_from_image
    doc_source = source_name or os.path.basename(file_path)
    source_slug = _slugify(doc_source)
    try:
        logger.info(f"Parsing Image {file_path} (Handwriting: {handwriting_mode}, Math: {math_mode})")
        if progress_callback:
            progress_callback("Running OCR/Handwriting Engine", 1, 1)
            
        image = Image.open(file_path)
        w, h = image.size
        
        # Copy image into image_dir so it can be embedded into generated notes
        saved_imgs = []
        if image_dir:
            os.makedirs(image_dir, exist_ok=True)
            ext = os.path.splitext(file_path)[1].lstrip('.').lower() or "png"
            dest_path = os.path.join(image_dir, f"{source_slug}_uploaded.{ext}")
            try:
                image.save(dest_path)
                saved_imgs.append({
                    "image_id": f"{source_slug}_uploaded",
                    "source": doc_source,
                    "page_number": 1,
                    "width": w,
                    "height": h,
                    "path": dest_path,
                    "caption": f"Uploaded diagram: {doc_source}",
                    "aspect_ratio": round(w / max(h, 1), 3)
                })
            except Exception as save_err:
                logger.debug(f"Could not copy uploaded image: {save_err}")
        
        if handwriting_mode:
            ocr_text = extract_handwritten_text(image)
            chunk_type = "handwriting_ocr"
        else:
            ocr_text = extract_text_from_image(image)
            chunk_type = "ocr"
            
        cleaned_text = clean_text(ocr_text)
        if math_mode or is_math_expression(cleaned_text):
            cleaned_text = format_math_text(cleaned_text)
            
        raw_blocks = [{"text": cleaned_text, "page_number": 1, "type": chunk_type, "images": saved_imgs}]
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
    source_name: Optional[str] = None,
    image_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Main document parsing router."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(file_path, progress_callback, math_mode, handwriting_mode, source_name=source_name, image_dir=image_dir)
    elif ext == ".docx":
        return parse_docx(file_path, progress_callback, math_mode, source_name=source_name, image_dir=image_dir)
    elif ext in [".txt", ".md"]:
        return parse_txt(file_path, progress_callback, math_mode, source_name=source_name, image_dir=image_dir)
    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        return parse_image(file_path, progress_callback, math_mode, handwriting_mode, source_name=source_name, image_dir=image_dir)
    else:
        raise ValueError(f"Unsupported file format '{ext}'")
