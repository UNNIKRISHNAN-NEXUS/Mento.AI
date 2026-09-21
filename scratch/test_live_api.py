# -*- coding: utf-8 -*-
"""
Live API Client Verification for Mento.AI Server.
Tests all endpoints:
- GET /api/health
- POST /api/upload
- GET /api/process/{task_id} (polling status)
- GET /api/results/{task_id}
- POST /api/generate/{task_id}
- GET /api/download/{task_id}
- GET /api/debug/{task_id}
"""

import sys
import os
import time
import requests

BASE_URL = "http://localhost:8000"

def test_live_api():
    print("=" * 60)
    print("  TESTING LIVE MENTO.AI API SERVER")
    print("=" * 60)
    
    # 1. Health check
    resp = requests.get(f"{BASE_URL}/api/health")
    print(f"[HEALTH CHECK] Status: {resp.status_code}, Response: {resp.json()}")
    assert resp.status_code == 200
    
    # 2. Upload test multi-page PDF & syllabus
    test_pdf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_artifacts", "test_5_pages.pdf")
    assert os.path.exists(test_pdf), f"Test PDF not found at {test_pdf}"
    
    files = [
        ("study_material", ("test_study.pdf", open(test_pdf, "rb"), "application/pdf"))
    ]
    data = {
        "syllabus_text": "Unit 1: Signals and Systems\n1. Introduction to Signal Processing\n2. Fourier Transform and Frequency Analysis",
        "threshold": 0.25,
        "math_mode": True,
        "handwriting_mode": False
    }
    
    print("\n[UPLOAD] Uploading study material and syllabus...")
    upload_resp = requests.post(f"{BASE_URL}/api/upload", files=files, data=data)
    print(f" -> Status: {upload_resp.status_code}, Response: {upload_resp.json()}")
    assert upload_resp.status_code == 200
    task_id = upload_resp.json().get("task_id")
    assert task_id, "Missing task_id in upload response"
    
    # 3. Poll processing status
    print(f"\n[PROGRESS] Polling progress for task {task_id}...")
    for _ in range(30):
        status_resp = requests.get(f"{BASE_URL}/api/process/{task_id}")
        data_json = status_resp.json()
        print(f" -> Progress: {data_json.get('progress')}% - {data_json.get('status')}")
        if data_json.get("progress") >= 100:
            break
        elif data_json.get("progress") == -1:
            raise RuntimeError(f"Processing failed: {data_json.get('status')}")
        time.sleep(1)
        
    # 4. Fetch results
    results_resp = requests.get(f"{BASE_URL}/api/results/{task_id}")
    print(f"\n[RESULTS] Status: {results_resp.status_code}")
    res_data = results_resp.json()
    topics = res_data.get("topics", [])
    print(f" -> Total Topics Returned: {len(topics)}")
    print(f" -> Syllabus Topics: {len(res_data.get('syllabus_topics', []))}")
    print(f" -> Other Topics: {len(res_data.get('other_topics', []))}")
    assert len(topics) > 0, "No topics returned in results"
    
    # 5. Generate PDF
    print(f"\n[GENERATE PDF] Requesting PDF generation...")
    gen_resp = requests.post(f"{BASE_URL}/api/generate/{task_id}", json={
        "export_format": "pdf",
        "selected_topic_ids": [t["topic_id"] for t in topics]
    })
    print(f" -> Status: {gen_resp.status_code}, Response: {gen_resp.json()}")
    assert gen_resp.status_code == 200
    
    # 6. Download PDF
    dl_resp = requests.get(f"{BASE_URL}/api/download/{task_id}?format=pdf")
    print(f"\n[DOWNLOAD PDF] Status: {dl_resp.status_code}, Content-Length: {len(dl_resp.content)} bytes")
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 1000, "Downloaded PDF is too small!"
    
    # 7. Check Diagnostics
    debug_resp = requests.get(f"{BASE_URL}/api/debug/{task_id}")
    print(f"\n[DEBUG / DIAGNOSTICS] Status: {debug_resp.status_code}")
    print(f" -> Diagnostics: {debug_resp.json()}")
    assert debug_resp.status_code == 200
    diag = debug_resp.json()
    assert diag.get("source_pages") == 5
    assert diag.get("output_pages") >= 2
    
    print("\n" + "=" * 60)
    print("  LIVE API SERVER VERIFICATION COMPLETED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    test_live_api()
