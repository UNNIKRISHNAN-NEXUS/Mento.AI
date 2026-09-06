---
name: mento-add-api-endpoint
description: >-
  Use when the user wants to add a new API route or endpoint to the Mento.AI
  backend. Covers the correct FastAPI patterns, where to register routes,
  how to integrate with the in-memory task store, and how to wire the frontend.
---

# Add a New API Endpoint to Mento.AI

## Backend: `backend/main.py`

All routes live here. Follow the existing pattern:

```python
@app.get("/api/my-endpoint/{task_id}")
async def my_endpoint(task_id: str):
    """Brief description of what this does."""
    if task_id not in tasks_results:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    data = tasks_results[task_id]
    # ... your logic ...
    return {"result": data}
```

### Key Patterns

| Need | Pattern |
|---|---|
| Read task progress | `tasks_progress.get(task_id, {})` |
| Read task results | `tasks_results.get(task_id)` |
| Return JSON | `return {"key": value}` |
| Return file | `return FileResponse(path, media_type=..., filename=...)` |
| SSE stream | `return StreamingResponse(generator(), media_type="text/event-stream")` |
| Background task | `background_tasks.add_task(fn, arg1, arg2)` |

### Receiving Files
```python
@app.post("/api/my-upload")
async def upload(files: List[UploadFile] = File(...)):
    for f in files:
        content = await f.read()
```

### Receiving JSON body
```python
from pydantic import BaseModel
class MyPayload(BaseModel):
    topic_ids: List[str]
    format: str = "docx"

@app.post("/api/my-json")
async def my_json(payload: MyPayload):
    ...
```

## Frontend: `frontend/js/app.js`

Wire the new endpoint in `app.js`:

```js
// GET request
const res = await fetch(`${API_BASE}/api/my-endpoint/${taskId}`);
const data = await res.json();

// POST with JSON
const res = await fetch(`${API_BASE}/api/my-json`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ topic_ids: [...], format: 'docx' })
});
```

## Verification

1. Restart the server (hot-reload picks up `main.py` changes automatically)
2. Test with PowerShell:
   ```powershell
   Invoke-RestMethod -Uri 'http://localhost:8000/api/my-endpoint/test123' | ConvertTo-Json
   ```
3. Check server logs for any tracebacks
