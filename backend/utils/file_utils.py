# -*- coding: utf-8 -*-
"""
Mento.AI File Utilities
Handles path definitions, upload/output directories, task ID generation, and cleanup.
"""

import os
import shutil
import tempfile
import time
import uuid
from typing import Tuple

# Detect Vercel environment
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))

# Define paths: Use /tmp on Vercel to avoid read-only filesystem errors
if IS_VERCEL:
    BASE_DIR = os.path.join(tempfile.gettempdir(), "mento_ai")
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# Ensure required directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_task_id() -> str:
    """Generate a unique ID for a document processing task."""
    return str(uuid.uuid4())

def get_task_paths(task_id: str) -> Tuple[str, str]:
    """
    Get the input directory and output directory for a specific task.
    Creates them if they do not exist.
    """
    task_upload_dir = os.path.join(UPLOAD_DIR, task_id)
    task_output_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_upload_dir, exist_ok=True)
    os.makedirs(task_output_dir, exist_ok=True)
    return task_upload_dir, task_output_dir

def clean_old_files(max_age_seconds: int = 3600):
    """
    Clean up uploaded and generated files older than max_age_seconds.
    Default: 1 hour.
    """
    current_time = time.time()
    for root_dir in [UPLOAD_DIR, OUTPUT_DIR]:
        if not os.path.exists(root_dir):
            continue
        for name in os.listdir(root_dir):
            path = os.path.join(root_dir, name)
            # Only clean up task-specific subdirectories
            if os.path.isdir(path) and len(name) == 36:  # length of UUID4 string
                try:
                    stat = os.stat(path)
                    # Check modified time or creation time
                    mtime = stat.st_mtime
                    if current_time - mtime > max_age_seconds:
                        shutil.rmtree(path)
                except Exception as e:
                    print(f"Error cleaning up path {path}: {e}")

def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Check if the file extension is in the allowed set."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions
