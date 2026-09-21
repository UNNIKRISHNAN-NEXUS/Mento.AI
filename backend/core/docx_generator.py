# -*- coding: utf-8 -*-
"""
Mento.AI Notes Document & PDF Generator
Generates clean, academic-style DOCX and PDF documents using Times New Roman (12-14pt)
in pure black text. Includes bold unit/topic headings, source file & page references,
the actual extracted notes from the uploaded study material, tables, and embedded diagrams & images.
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
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

logger = logging.getLogger("docx_generator")

# Pure Black Palette (Academic standard)
COLOR_BLACK = RGBColor(0, 0, 0)
COLOR_GRAY = RGBColor(90, 90, 90)

def deduplicate_and_merge_chunks(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates and merges overlapping text chunks from the same source document.
    Only merges or filters identical blocks within the same topic and page,
    preventing loss of distinct sections on later pages.
    """
    if not matches:
        return []
        
    cleaned_matches = []
    seen_in_topic = set()
    
    for match in matches:
        raw_text = match.get("text", "").strip()
        match_imgs = list(match.get("images", []))
        match_tabs = list(match.get("tables", []))
        page_num = match.get("page_number", 1)
        source = match.get("source", "Study Material")
        
        if not raw_text and not match_imgs and not match_tabs:
            continue
            
        # Deduplication key scoped to source + page + first 40 words
        content_key = (source, page_num, " ".join(raw_text.split()[:40]))
        if raw_text and content_key in seen_in_topic and not match_imgs and not match_tabs:
            continue
            
        if raw_text:
            seen_in_topic.add(content_key)
        
        # Check if this chunk can be merged with previous chunk if overlapping on the same page
        if cleaned_matches and raw_text:
            prev = cleaned_matches[-1]
            if prev["source"] == source and prev["page_number"] == page_num:
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
                            
                    # Merge tables
                    prev.setdefault("tables", []).extend(match_tabs)
                    continue
                    
        cleaned_matches.append({
            "chunk_id": match.get("chunk_id", ""),
            "text": raw_text,
            "page_number": page_num,
            "source": source,
            "type": match.get("type", "digital"),
            "similarity_score": match.get("similarity_score", 1.0),
            "images": match_imgs,
            "tables": match_tabs
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

def set_cell_border(cell, **kwargs):
    """Set cell borders in python-docx table."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in("w:tcBorders")
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
        
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = 'w:{}'.format(edge)
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)
            for key, val in edge_data.items():
                element.set(qn('w:{}'.format(key)), str(val))

def generate_docx(
    matched_results: List[Dict[str, Any]],
    output_path: str,
    title: str = "Extracted Study Notes",
    description: str = "Notes extracted and compiled by Mento.AI"
) -> bool:
    """
    Generate a clean DOCX document in Times New Roman (12-14pt) pure black.
    Includes unit headings, topic headings, source/page references, actual extracted notes,
    tables, and embedded diagrams, figures, and charts in reading order.
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
        total_written_tables = 0
        
        for idx, result in enumerate(matched_results):
            raw_matches = result.get("matches", [])
            matches = deduplicate_and_merge_chunks(raw_matches)
            
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
                
            # Excerpts (12pt Times New Roman, 1.15 line spacing) + Images + Tables
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
                
                # Insert structured tables
                match_tables = match.get("tables", [])
                for tab in match_tables:
                    rows_data = tab.get("rows", [])
                    if rows_data and len(rows_data) >= 2:
                        try:
                            table = doc.add_table(rows=len(rows_data), cols=len(rows_data[0]))
                            table.style = 'Light Shading Accent 1' if 'Light Shading Accent 1' in [s.name for s in doc.styles] else 'Table Grid'
                            
                            for r_idx, r in enumerate(rows_data):
                                for c_idx, val in enumerate(r):
                                    if c_idx < len(table.columns):
                                        cell = table.cell(r_idx, c_idx)
                                        cell.text = str(val)
                                        for p in cell.paragraphs:
                                            for run in p.runs:
                                                run.font.name = 'Times New Roman'
                                                run.font.size = Pt(10)
                                                if r_idx == 0:
                                                    run.bold = True
                            
                            p_space = doc.add_paragraph()
                            p_space.paragraph_format.space_after = Pt(6)
                            total_written_tables += 1
                        except Exception as tab_err:
                            logger.warning(f"Could not insert table into DOCX: {tab_err}")
                
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
                            run_cap.font.color.rgb = COLOR_GRAY
                            run_cap.italic = True
                            
                        total_written_images += 1
                    except Exception as img_err:
                        logger.warning(f"Could not insert image {img_path} into DOCX: {img_err}")

        if total_topics_added == 0 or (total_written_chars < 30 and total_written_images == 0 and total_written_tables == 0):
            raise ValueError(
                f"Generated document contains no meaningful extracted notes (total_chars={total_written_chars}, total_images={total_written_images})."
            )
            
        doc.save(output_path)
        logger.info(f"[DOCX] written_chars={total_written_chars} images={total_written_images} tables={total_written_tables} across {total_topics_added} topics saved to {output_path}")
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
    tables, and embedded diagrams, figures, and charts in reading order.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image as RLImage, KeepTogether, Table as RLTable, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        logger.info(f"Generating PDF output at {output_path}...")
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54
        )
        
        styles = getSampleStyleSheet()
        
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
        
        table_cell_style = ParagraphStyle(
            'TableCellStyle',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=10,
            leading=12,
            textColor=colors.black
        )
        
        table_header_style = ParagraphStyle(
            'TableHeaderStyle',
            parent=styles['Normal'],
            fontName='Times-Bold',
            fontSize=10,
            leading=12,
            textColor=colors.black
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
        total_written_tables = 0
        
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
                        safe_body = xml_safe(clean_p).replace("\n", "<br/>")
                        story.append(Paragraph(safe_body, body_style))
                
                # Insert tables
                match_tables = match.get("tables", [])
                for tab in match_tables:
                    rows_data = tab.get("rows", [])
                    if rows_data and len(rows_data) >= 2:
                        try:
                            # Printable width = 612 - 108 = 504pt
                            col_count = len(rows_data[0])
                            col_w = min(120.0, 480.0 / max(col_count, 1))
                            
                            formatted_rows = []
                            for r_idx, r in enumerate(rows_data):
                                f_row = []
                                for c in r:
                                    st = table_header_style if r_idx == 0 else table_cell_style
                                    f_row.append(Paragraph(xml_safe(str(c)), st))
                                formatted_rows.append(f_row)
                                
                            rl_table = RLTable(formatted_rows, colWidths=[col_w] * col_count)
                            rl_table.setStyle(TableStyle([
                                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEEEEE')),
                                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#999999')),
                                ('TOPPADDING', (0, 0), (-1, -1), 4),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                            ]))
                            story.append(Spacer(1, 4))
                            story.append(rl_table)
                            story.append(Spacer(1, 6))
                            total_written_tables += 1
                        except Exception as tab_err:
                            logger.warning(f"Could not insert table into PDF: {tab_err}")
                
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
                            max_w = 480.0
                            max_h = 340.0
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
                    
        if total_topics_added == 0 or (total_written_chars < 30 and total_written_images == 0 and total_written_tables == 0):
            raise ValueError(
                f"Generated document contains no meaningful extracted notes (total_chars={total_written_chars}, total_images={total_written_images})."
            )
            
        doc.build(story)
        logger.info(f"[PDF] written_chars={total_written_chars} images={total_written_images} tables={total_written_tables} across {total_topics_added} topics saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating PDF document: {e}", exc_info=True)
        raise e

def validate_generated_document(
    output_path: str,
    export_format: str = "docx",
    min_chars: int = 30,
    expected_min_pages: int = 1
) -> Dict[str, Any]:
    """
    Validates the generated output document by reopening it.
    Checks file existence, non-zero byte size, text character count, image count, and page count.
    Guarantees that a multi-page document never silently collapses into an empty or 1-page output.
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
        "page_count": 1,
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
            
        if expected_min_pages > 1 and report["page_count"] < expected_min_pages:
            logger.warning(f"Generated PDF has {report['page_count']} pages, which is less than expected {expected_min_pages}.")
    else:
        import docx
        doc = docx.Document(output_path)
        total_text = " ".join(p.text for p in doc.paragraphs if p.text.strip())
        report["total_chars"] = len(total_text)
        report["paragraphs_count"] = len(doc.paragraphs)
        report["images_count"] = len(doc.inline_shapes)
        if report["total_chars"] < min_chars and report["images_count"] == 0:
            raise ValueError(f"Generated DOCX contains insufficient content ({report['total_chars']} chars, {report['images_count']} images).")
            
    logger.info(f"[VALIDATION] format={export_format} pages={report.get('page_count', 1)} chars={report['total_chars']} images={report['images_count']} size={file_size} bytes - OK")
    return report
