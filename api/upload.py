# -*- coding: utf-8 -*-
"""
Vercel Serverless Function for /api/upload
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
