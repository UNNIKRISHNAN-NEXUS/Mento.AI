---
name: mento-debug-ai-pipeline
description: >-
  Use when the user is debugging the AI processing pipeline: SBERT encoding,
  FAISS search, topic matching, SSE progress streaming, or when results are
  empty, wrong topics are matched, or processing hangs. Also use when tuning
  the similarity threshold or top_k parameters.
---

# Debug the Mento.AI AI Pipeline

## Pipeline Overview

```
Upload → parser.py → syllabus_parser.py → matcher.py → results stored → SSE done signal
```

## Step 1: Isolate the Stage

Run a quick pipeline test with the existing test files:

```powershell
backend\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.')
from backend.core.parser import parse_document
from backend.core.syllabus_parser import parse_syllabus
from backend.core.matcher import match_syllabus_to_document, compute_coverage_audit

chunks = parse_document('test_study.txt')
print(f'Chunks extracted: {len(chunks)}')
if chunks: print('Sample:', chunks[0]['text'][:80])

topics = parse_syllabus('test_syllabus.txt')
print(f'Topics found: {len(topics)}')
if topics: print('First:', topics[0])

results = match_syllabus_to_document(topics, chunks, similarity_threshold=0.2, top_k=3)
print(f'Topics matched: {sum(1 for r in results if r[\"matches\"])} / {len(results)}')
for r in results[:2]:
    print(f'  {r[\"title\"]}: {len(r[\"matches\"])} matches')
    if r['matches']:
        print(f'    Best score: {r[\"matches\"][0][\"similarity_score\"]:.3f}')
"
```

## Common Problems & Fixes

### Problem: No topics matched (all empty results)
**Causes:**
1. Threshold too high — try lowering to `0.15` or `0.20`
2. Study material too short / not enough chunks
3. Syllabus topics too abstract vs material content

**Debug threshold:**
```python
results = match_syllabus_to_document(topics, chunks, similarity_threshold=0.15)
```

### Problem: Processing hangs at 70% ("Initializing AI semantic models")
**Cause:** First-run SBERT download from HuggingFace. Wait ~60–120 seconds.
**Check model cache:**
```powershell
ls $env:USERPROFILE\.cache\huggingface\hub\
```
If empty, the model is still downloading.

### Problem: Wrong topics are matched
**Cause:** The `full_context` field in syllabus topics is used for embedding (not just the topic title). Check what `parse_syllabus` returns:
```python
topics = parse_syllabus('my_syllabus.txt')
for t in topics:
    print(t['full_context'])
```

### Problem: SSE stream shows no progress updates in browser
**Cause:** Browser or nginx buffering SSE. The SSE endpoint is `/api/process/{task_id}`.
Check the response in console:
```js
const es = new EventSource('/api/process/TASK_ID');
es.onmessage = e => console.log(JSON.parse(e.data));
```

### Problem: `similarity_score` missing from match result
**Fix:** Ensure `matcher.py` includes both `score` and `similarity_score` in each match dict.
```python
topic_matches.append({
    ...
    "score": round(score, 4),
    "similarity_score": round(score, 4),  # alias for frontend
    "confidence_pct": round(score * 100, 1)
})
```

## Tuning Parameters

| Parameter | Default | Effect |
|---|---|---|
| `similarity_threshold` | 0.35 | Lower = more (possibly irrelevant) matches |
| `top_k` | 5 | Max excerpts per topic |
| Chunk size | ~200–500 chars | Set in `parser.py` |

## Checking Logs

The server logs all pipeline steps. Look for:
```
INFO:main: Task abc123: Parsing syllabus...
INFO:main: Syllabus parsed. 12 topics found.
INFO:matcher: Embedding 847 document chunks...
INFO:matcher: FAISS vector index built successfully.
INFO:matcher: Running vector similarity search (top_k=5, threshold=0.35)...
INFO:matcher: Syllabus-to-document matching completed.
```
Any `ERROR:` line indicates a failure with a full traceback.
