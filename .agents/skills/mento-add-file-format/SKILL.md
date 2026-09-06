---
name: mento-add-file-format
description: >-
  Use when the user wants to add support for a new file format (e.g., .pptx,
  .epub, .md, .html) to the study material or syllabus upload. Covers all
  layers that need updating: parser.py, main.py allowed extensions, and
  frontend accept attributes.
---

# Add a New File Format to Mento.AI

Adding a new parseable format requires changes in 3 places.

## Step 1: `backend/core/parser.py`

Add a new branch in the `parse_document()` function:

```python
elif ext == ".pptx":
    # Example: python-pptx
    from pptx import Presentation
    prs = Presentation(file_path)
    text_blocks = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                text_blocks.append(shape.text_frame.text)
    full_text = "\n".join(text_blocks)
    chunks = split_into_chunks(full_text, source=os.path.basename(file_path))
    return chunks
```

Follow the existing pattern — each branch must return a list of chunk dicts:
```python
{
    "chunk_id": f"{source}_{page}_{idx}",
    "text": "...",
    "page_number": 1,
    "type": "text",
    "source": "filename.ext"
}
```

## Step 2: `backend/main.py`

Add the extension to the allowed set:
```python
ALLOWED_DOCS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".pptx"}
```

## Step 3: `frontend/index.html`

Update both file inputs' `accept` attribute:
```html
<!-- Study material input -->
<input type="file" id="study-material-input"
       accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp,.pptx" multiple ...>

<!-- Syllabus input -->
<input type="file" id="syllabus-input"
       accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp,.pptx" ...>
```

## Step 4: `frontend/js/app.js`

Update the allowed extensions array:
```js
const ALLOWED_EXTS = ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg', '.webp', '.pptx'];
```

## Step 5: Install the New Library (if needed)

```powershell
backend\.venv\Scripts\python.exe -m pip install python-pptx
# Then add to requirements.txt:
backend\.venv\Scripts\python.exe -m pip freeze | Select-String "pptx" | Out-File -Append requirements.txt
```

## Verification

```powershell
# Quick test
backend\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.')
from backend.core.parser import parse_document
chunks = parse_document('your_test_file.pptx')
print(f'Chunks: {len(chunks)}')
if chunks: print('First:', chunks[0]['text'][:100])
"
```
