# -*- coding: utf-8 -*-
"""
Mento.AI Notes Document & PDF Generator
Generates clean, academic-style DOCX and PDF documents using Times New Roman (12-14pt)
in pure black text. Includes bold unit/topic headings, source file & page references,
the actual extracted notes from the uploaded study material, and embedded diagrams & images.
Includes post-generation content validation to guarantee document integrity.
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger("docx_generator")

# Pure Black Palette (Academic standard)
COLOR_BLACK = RGBColor(0, 0, 0)

def deduplicate_and_merge_chunks(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates and merges overlapping text chunks from the same source document.
    Preserves original reading order, page numbers, formatting, and associated images.
    """
    if not matches:
        return []
        
    cleaned_matches = []
    seen_texts = set()
    
    for match in matches:
        raw_text = match.get("text", "").strip()
        match_imgs = list(match.get("images", []))
        
        if not raw_text and not match_imgs:
            continue
            
        # Normalize for duplicate detection
        normalized = " ".join(raw_text.split()[:25]) if raw_text else f"img_only_{match.get('chunk_id')}"
        if normalized in seen_texts and not match_imgs:
            continue
            
        seen_texts.add(normalized)
        
        # Check if this chunk can be merged with previous chunk if overlapping
        if cleaned_matches and raw_text:
            prev = cleaned_matches[-1]
            if prev["source"] == match.get("source") and prev["page_number"] == match.get("page_number"):
                prev_text = prev["text"]
                prev_tail = prev_text[-100:].strip()
                curr_head = raw_text[:100].strip()
                
                overlap_len = 0
                for length in range(min(len(prev_tail), len(curr_head)), 15, -1):
                    if prev_tail.endswith(curr_head[:length]):
                        overlap_len = length
                        break
                        
                if overlap_len > 0:
                    merged_text = prev_text + raw_text[overlap_len:]
                    prev["text"] = merged_text
                    
                    # Merge images without duplicates
                    existing_img_ids = {img.get("image_id") or img.get("path") for img in prev.get("images", [])}
                    for img in match_imgs:
                        img_id = img.get("image_id") or img.get("path")
                        if img_id not in existing_img_ids:
                            existing_img_ids.add(img_id)
                            prev["images"].append(img)
                    continue
                    
        cleaned_matches.append({
            "chunk_id": match.get("chunk_id", ""),
            "text": raw_text,
            "page_number": match.get("page_number", 1),
            "source": match.get("source", "Study Material"),
            "type": match.get("type", "digital"),
            "similarity_score": match.get("similarity_score", 1.0),
            "images": match_imgs
        })
        
    return cleaned_matches

def add_heading_times(doc, text: str, level: int, space_before: int = 14, space_after: int = 4):
    """Add a heading styled in Times New Roman Bold Pure Black."""
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    
    font_size = 15 if level == 1 else 13
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(font_size)
        run.font.color.rgb = COLOR_BLACK
        run.bold = True
        
    return p

def generate_docx(
    matched_results: List[Dict[str, Any]],
    output_path: str,
    title: str = "Extracted Study Notes",
    description: str = "Notes extracted and compiled by Mento.AI"
) -> bool:
    """
    Generate a clean DOCX document in Times New Roman (12-14pt) pure black.
    Includes unit headings, topic headings, source/page references, actual extracted notes,
    and embedded diagrams, figures, and charts in reading order.
    """
    try:
        logger.info(f"Generating DOCX output at {output_path}...")
        doc = docx.Document()
        
        # Page Margins (1 inch all sides)
        for section in doc.sections:
            section.page_width = Inches(8.5)
            section.page_height = Inches(11.0)
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)
            
        # Set Normal style to Times New Roman 12pt Pure Black
        style_normal = doc.styles['Normal']
        style_normal.font.name = 'Times New Roman'
        style_normal.font.size = Pt(12)
        style_normal.font.color.rgb = COLOR_BLACK
        style_normal.paragraph_format.line_spacing = 1.15
        style_normal.paragraph_format.space_after = Pt(6)
        
        # Title Block
        title_p = doc.add_paragraph()
        title_p.paragraph_format.space_before = Pt(12)
        title_p.paragraph_format.space_after = Pt(4)
        title_run = title_p.add_run(f"MENTO.AI — {title.upper()}")
        title_run.font.name = 'Times New Roman'
        title_run.font.size = Pt(18)
        title_run.font.color.rgb = COLOR_BLACK
        title_run.bold = True
        
        # Subtitle / Source info
        desc_p = doc.add_paragraph()
        desc_p.paragraph_format.space_after = Pt(14)
        desc_run = desc_p.add_run(f"{description} | Generated on {datetime.now().strftime('%B %d, %Y')}")
        desc_run.font.name = 'Times New Roman'
        desc_run.font.size = Pt(10.5)
        desc_run.font.color.rgb = COLOR_BLACK
        desc_run.italic = True
        
        # Horizontal divider line
        div_p = doc.add_paragraph()
        div_p.paragraph_format.space_after = Pt(16)
        div_run = div_p.add_run("_________________________________________________________________________________")
        div_run.font.name = 'Times New Roman'
        div_run.font.size = Pt(9)
        div_run.font.color.rgb = COLOR_BLACK
        
        current_unit = None
        total_topics_added = 0
        total_written_chars = 0
        total_written_images = 0
        
        for idx, result in enumerate(matched_results):
            raw_matches = result.get("matches", [])
            matches = deduplicate_and_merge_chunks(raw_matches)
            
            # Skip topics with no extractable content
            if not matches:
                continue
                
            total_topics_added += 1
            unit_name = result.get("unit", "General")
            
            # Unit Heading (15pt Bold Times New Roman)
            if unit_name != current_unit:
                current_unit = unit_name
                add_heading_times(doc, current_unit.upper(), level=1, space_before=18, space_after=6)
                
            # Topic Heading (13pt Bold Times New Roman)
            topic_number = result.get("hierarchy_number", "")
            topic_title = result.get("title", "")
            if topic_number and topic_number != "*":
                heading_text = f"Topic {topic_number}: {topic_title}"
            else:
                heading_text = f"Topic: {topic_title}"
                
            add_heading_times(doc, heading_text, level=2, space_before=12, space_after=4)
                
            # Excerpts (12pt Times New Roman, 1.15 line spacing) + Images
            for m_idx, match in enumerate(matches):
                # Source and Page Reference
                p_meta = doc.add_paragraph()
                p_meta.paragraph_format.space_before = Pt(4)
                p_meta.paragraph_format.space_after = Pt(2)
                p_meta.paragraph_format.keep_with_next = True
                
                meta_run = p_meta.add_run(
                    f"Source: {match['source']} | Page: {match['page_number']}"
                )
                meta_run.font.name = 'Times New Roman'
                meta_run.font.size = Pt(10)
                meta_run.font.color.rgb = COLOR_BLACK
                meta_run.italic = True
                
                # Excerpt Body Text
                text_content = match.get("text", "")
                if text_content:
                    total_written_chars += len(text_content)
                    paragraphs = text_content.split("\n\n")
                    
                    for text_block in paragraphs:
                        clean_block = text_block.strip()
                        if not clean_block:
                            continue
                        p_block = doc.add_paragraph()
                        p_block.paragraph_format.space_after = Pt(6)
                        p_block.paragraph_format.left_indent = Inches(0.15)
                        
                        run = p_block.add_run(clean_block)
                        run.font.name = 'Times New Roman'
                        run.font.size = Pt(12)
                        run.font.color.rgb = COLOR_BLACK
                
                # Insert associated images
                match_images = match.get("images", [])
                for img in match_images:
                    img_path = img.get("path")
                    if not img_path or not os.path.exists(img_path):
                        continue
                    try:
                        with Image.open(img_path) as pil_img:
                            iw, ih = pil_img.size
                            if iw <= 0 or ih <= 0:
                                continue
                            aspect = iw / max(ih, 1)
                            # Fit into printable width (max 5.8 inches)
                            if aspect >= 1.0:
                                disp_w = min(5.8, max(2.5, iw / 96.0))
                            else:
                                disp_w = min(4.0, max(2.0, iw / 96.0))
                                
                        p_img = doc.add_paragraph()
                        p_img.paragraph_format.space_before = Pt(8)
                        p_img.paragraph_format.space_after = Pt(3)
                        p_img.paragraph_format.left_indent = Inches(0.15)
                        
                        run_img = p_img.add_run()
                        run_img.add_picture(img_path, width=Inches(disp_w))
                        
                        caption = img.get("caption", "").strip()
                        if caption:
                            p_cap = doc.add_paragraph()
                            p_cap.paragraph_format.space_after = Pt(8)
                            p_cap.paragraph_format.left_indent = Inches(0.15)
                            run_cap = p_cap.add_run(caption)
                            run_cap.font.name = 'Times New Roman'
                            run_cap.font.size = Pt(10)
                            run_cap.font.color.rgb = RGBColor(90, 90, 90)
                            run_cap.italic = True
                            
                        total_written_images += 1
                    except Exception as img_err:
                        logger.warning(f"Could not insert image {img_path} into DOCX: {img_err}")

        if total_topics_added == 0 or (total_written_chars < 40 and total_written_images == 0):
            raise ValueError(
                f"Generated document contains no meaningful extracted notes (total_chars={total_written_chars}, total_images={total_written_images})."
            )
            
        doc.save(output_path)
        logger.info(f"[DOCX] written_chars={total_written_chars} images={total_written_images} across {total_topics_added} topics saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating DOCX document: {e}", exc_info=True)
        raise e

def generate_pdf(
    matched_results: List[Dict[str, Any]],
    output_path: str,
    title: str = "Extracted Study Notes",
    description: str = "Notes extracted and compiled by Mento.AI"
) -> bool:
    """
    Generate a clean PDF document using ReportLab in Times-Roman (12-14pt) pure black.
    Includes unit headings, topic headings, source/page references, extracted notes,
    and embedded diagrams, figures, and charts in reading order.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image as RLImage, KeepTogether
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        logger.info(f"Generating PDF output at {output_path}...")
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=72,
            rightMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        styles = getSampleStyleSheet()
        
        # Pure Black Times-Roman Styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontName='Times-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.black,
            spaceAfter=4
        )
        
        desc_style = ParagraphStyle(
            'DescStyle',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=10.5,
            leading=14,
            textColor=colors.black,
            spaceAfter=12
        )
        
        unit_style = ParagraphStyle(
            'UnitStyle',
            parent=styles['Heading1'],
            fontName='Times-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.black,
            spaceBefore=16,
            spaceAfter=6,
            keepWithNext=True
        )
        
        topic_style = ParagraphStyle(
            'TopicStyle',
            parent=styles['Heading2'],
            fontName='Times-Bold',
            fontSize=13,
            leading=17,
            textColor=colors.black,
            spaceBefore=10,
            spaceAfter=3,
            keepWithNext=True
        )
        
        meta_style = ParagraphStyle(
            'MetaStyle',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=10,
            leading=13,
            textColor=colors.black,
            spaceBefore=3,
            spaceAfter=3,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=11.5,
            leading=15,
            textColor=colors.black,
            leftIndent=12,
            spaceAfter=6
        )
        
        caption_style = ParagraphStyle(
            'CaptionStyle',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor('#444444'),
            leftIndent=12,
            spaceBefore=2,
            spaceAfter=8
        )
        
        def xml_safe(t: str) -> str:
            if not t:
                return ""
            s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(t))
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        story = []
        
        # Title Block
        story.append(Paragraph(xml_safe(f"MENTO.AI — {title.upper()}"), title_style))
        story.append(Paragraph(xml_safe(f"{description} | Generated on {datetime.now().strftime('%B %d, %Y')}"), desc_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=0, spaceAfter=14))
        
        current_unit = None
        total_topics_added = 0
        total_written_chars = 0
        total_written_images = 0
        
        for result in matched_results:
            raw_matches = result.get("matches", [])
            matches = deduplicate_and_merge_chunks(raw_matches)
            
            if not matches:
                continue
                
            total_topics_added += 1
            unit_name = result.get("unit", "General")
            
            if unit_name != current_unit:
                current_unit = unit_name
                story.append(Paragraph(xml_safe(current_unit.upper()), unit_style))
                
            topic_number = result.get("hierarchy_number", "")
            topic_title = result.get("title", "")
            if topic_number and topic_number != "*":
                heading_text = f"Topic {topic_number}: {topic_title}"
            else:
                heading_text = f"Topic: {topic_title}"
                
            story.append(Paragraph(xml_safe(heading_text), topic_style))
                
            for match in matches:
                meta_text = f"Source: {match['source']} | Page: {match['page_number']}"
                story.append(Paragraph(xml_safe(meta_text), meta_style))
                
                text_content = match.get("text", "")
                if text_content:
                    total_written_chars += len(text_content)
                    paragraphs = text_content.split("\n\n")
                    for p_text in paragraphs:
                        clean_p = p_text.strip()
                        if not clean_p:
                            continue
                        story.append(Paragraph(xml_safe(clean_p), body_style))
                
                # Insert associated images
                match_images = match.get("images", [])
                for img in match_images:
                    img_path = img.get("path")
                    if not img_path or not os.path.exists(img_path):
                        continue
                    try:
                        with Image.open(img_path) as pil_img:
                            iw, ih = pil_img.size
                            if iw <= 0 or ih <= 0:
                                continue
                            # Page printable width = 612 - 144 = 468pt
                            max_w = 445.0
                            max_h = 320.0
                            scale = min(max_w / iw, max_h / ih, 1.0)
                            final_w = iw * scale
                            final_h = ih * scale
                            
                        img_flowables = [
                            Spacer(1, 4),
                            RLImage(img_path, width=final_w, height=final_h)
                        ]
                        
                        caption = img.get("caption", "").strip()
                        if caption:
                            img_flowables.append(Paragraph(xml_safe(caption), caption_style))
                        else:
                            img_flowables.append(Spacer(1, 6))
                            
                        story.append(KeepTogether(img_flowables))
                        total_written_images += 1
                    except Exception as img_err:
                        logger.warning(f"Could not insert image {img_path} into PDF: {img_err}")
                    
        if total_topics_added == 0 or (total_written_chars < 40 and total_written_images == 0):
            raise ValueError(
                f"Generated document contains no meaningful extracted notes (total_chars={total_written_chars}, total_images={total_written_images})."
            )
            
        doc.build(story)
        logger.info(f"[PDF] written_chars={total_written_chars} images={total_written_images} across {total_topics_added} topics saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating PDF document: {e}", exc_info=True)
        raise e

def validate_generated_document(
    output_path: str,
    export_format: str = "docx",
    min_chars: int = 40
) -> Dict[str, Any]:
    """
    Validates the generated output document to ensure it exists, is not empty,
    and contains extracted content (text and/or images).
    """
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"Generated file not found at {output_path}")
        
    file_size = os.path.getsize(output_path)
    if file_size < 300:
        raise ValueError(f"Generated file is too small ({file_size} bytes), likely corrupted.")
        
    report = {
        "valid": True,
        "format": export_format.lower(),
        "file_size_bytes": file_size,
        "total_chars": 0,
        "images_count": 0
    }
    
    if export_format.lower() == "pdf":
        import pymupdf
        doc = pymupdf.open(output_path)
        report["page_count"] = len(doc)
        total_text = ""
        total_imgs = 0
        for page in doc:
            total_text += page.get_text("text") or ""
            total_imgs += len(page.get_images())
        doc.close()
        
        report["total_chars"] = len(total_text.strip())
        report["images_count"] = total_imgs
        if report["total_chars"] < min_chars and total_imgs == 0:
            raise ValueError(f"Generated PDF contains insufficient content ({report['total_chars']} chars, {total_imgs} images).")
    else:
        import docx
        doc = docx.Document(output_path)
        total_text = " ".join(p.text for p in doc.paragraphs if p.text.strip())
        report["total_chars"] = len(total_text)
        report["paragraphs_count"] = len(doc.paragraphs)
        report["images_count"] = len(doc.inline_shapes)
        if report["total_chars"] < min_chars and report["images_count"] == 0:
            raise ValueError(f"Generated DOCX contains insufficient content ({report['total_chars']} chars, {report['images_count']} images).")
            
    logger.info(f"[VALIDATION] format={export_format} chars={report['total_chars']} images={report['images_count']} size={file_size} bytes - OK")
    return report
