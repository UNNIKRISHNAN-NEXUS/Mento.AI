# -*- coding: utf-8 -*-
"""
Vercel Serverless Function entrypoint for Mento.AI FastAPI backend.
"""
import sys
import os

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
