#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mento.AI — Application Launcher

Local:
    python run.py
    → http://localhost:8000

Render:
    Render automatically provides the PORT environment variable.
"""

import sys
import os
import uvicorn

# ---------------------------------------------------------
# Add project root to Python path
# ---------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------
# Start FastAPI application
# ---------------------------------------------------------

if __name__ == "__main__":

    # Render provides PORT automatically.
    # Locally, fall back to 8000.
    port = int(os.environ.get("PORT", 8000))

    print("\n" + "=" * 60)
    print("  Mento.AI -- AI-Powered Syllabus Notes Extractor")
    print("=" * 60)
    print(f"  Server starting on port: {port}")
    print("  Host: 0.0.0.0")
    print("=" * 60 + "\n")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port
    )
