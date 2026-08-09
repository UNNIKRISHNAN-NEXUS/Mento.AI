#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mento.AI — Application Launcher
Run this script from the project root to start the server.

Usage:
    python run.py

Then open http://localhost:8000 in your browser.
"""

import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  Mento.AI -- AI-Powered Syllabus Notes Extractor")
    print("=" * 60)
    print("  Server starting at: http://localhost:8000")
    print("  Press Ctrl+C to stop.")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.join(project_root, "backend")]
    )
