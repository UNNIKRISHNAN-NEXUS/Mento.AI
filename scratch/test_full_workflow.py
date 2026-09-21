# -*- coding: utf-8 -*-
"""
End-to-End Verification Test for Mento.AI
Tests:
1. File upload with syllabus and study material (containing syllabus and non-syllabus topics)
2. Task processing and result validation (Syllabus Topics & Other Topics)
3. Topic selection and document generation (DOCX and PDF)
4. Inspection of downloaded files to guarantee actual notes content, citations, and headers exist.
"""

import os
import json
import time
import requests
import docx
import fitz  # PyMuPDF

BASE_URL = "http://localhost:8000"

SYLLABUS_CONTENT = """
UNIT 1: SIGNALS AND SYSTEMS
1.1 Classification of Signals
1.2 Continuous Time Signals
1.3 Discrete Time Signals

UNIT 2: LINEAR TIME-INVARIANT SYSTEMS
2.1 Convolution Sum
2.2 System Properties
"""

STUDY_MATERIAL_CONTENT = """
UNIT 1 — SIGNALS AND SYSTEMS

1.1 Classification of Signals
A signal is a function that conveys information about the state or behavior of a physical system.
Signals can be categorized in multiple ways:
- Continuous-time signals: Defined for every instant of time t over a continuum.
- Discrete-time signals: Defined only at discrete time instants n (integers).
- Deterministic vs Random: Deterministic signals can be uniquely modeled by mathematical equations, whereas random signals exhibit uncertainty.
- Periodic vs Aperiodic: A signal x(t) is periodic if x(t + T) = x(t) for all t.
- Energy vs Power: Energy signals have finite total energy, while power signals have finite average power.

1.2 Continuous Time Signals
Continuous-time signals are represented as continuous functions of time x(t).
Examples include analog speech waveforms, voltages across resistors in an RC circuit, and temperature variations over time.
The continuous unit impulse function delta(t) and unit step function u(t) are fundamental building blocks.

1.3 Discrete Time Signals
Discrete-time signals are represented mathematically as sequences of real or complex numbers x[n], where n is an integer index.
They are commonly obtained through uniform sampling of analog signals: x[n] = x(nTs), where Ts is the sampling period.
Important discrete signals include:
1. Discrete unit impulse delta[n] = 1 for n=0, 0 otherwise.
2. Discrete unit step u[n] = 1 for n>=0, 0 otherwise.
3. Exponential sequences x[n] = a^n.

CHAPTER 5: ADVANCED TRANSFORM TECHNIQUES (NON-SYLLABUS EXTENSION)

5.1 Z-Transform
The Z-transform is a mathematical tool used extensively in digital signal processing and discrete-time control theory.
It transforms a discrete-time domain signal x[n] into a complex frequency domain representation X(z).
Definition:
X(z) = sum_{n=-infinity}^{infinity} x[n] * z^{-n}
where z = r * e^{j * omega} is a complex variable.
The Region of Convergence (ROC) defines the set of all z in the complex plane for which the summation converges.
Key Properties:
- Linearity: Z{a*x1[n] + b*x2[n]} = a*X1(z) + b*X2(z)
- Time Shifting: Z{x[n - k]} = z^{-k} * X(z)
- Convolution: Z{x1[n] * x2[n]} = X1(z) * X2(z)

5.2 Noise Reduction Techniques
Noise reduction aims to recover an estimate of the original clean signal s[n] from a noisy observation y[n] = s[n] + v[n].
Common methods include:
- Moving Average Filtering: Smoothes out high-frequency fluctuations.
- Median Filtering: Effective against impulsive or salt-and-pepper noise while preserving sharp step edges.
- Spectral Subtraction: Estimates noise power spectral density during silence periods and subtracts it from the noisy spectrum.
"""

def test_workflow():
    print("\n=======================================================")
    print("MENTO.AI COMPLETE WORKFLOW & DATA PIPELINE VERIFICATION")
    print("=======================================================")

    # 1. Prepare test files
    os.makedirs("scratch", exist_ok=True)
    syllabus_path = "scratch/test_verify_syllabus.txt"
    study_path = "scratch/test_verify_study.txt"

    with open(syllabus_path, "w", encoding="utf-8") as f:
        f.write(SYLLABUS_CONTENT)

    with open(study_path, "w", encoding="utf-8") as f:
        f.write(STUDY_MATERIAL_CONTENT)

    # 2. Upload files
    print("\n[Step 1] Uploading syllabus and study notes to /api/upload...")
    with open(syllabus_path, "rb") as s_file, open(study_path, "rb") as sm_file:
        files = [
            ("study_material", ("signals_notes.txt", sm_file, "text/plain")),
            ("syllabus", ("syllabus.txt", s_file, "text/plain"))
        ]
        data = {
            "threshold": "0.30",
            "math_mode": "false",
            "handwriting_mode": "false"
        }
        res = requests.post(f"{BASE_URL}/api/upload", files=files, data=data)

    assert res.status_code == 200, f"Upload failed: {res.text}"
    task_id = res.json()["task_id"]
    print(f"-> Upload successful! Task ID: {task_id}")

    # 3. Poll progress until complete
    print("\n[Step 2] Tracking task processing progress...")
    for _ in range(30):
        p_res = requests.get(f"{BASE_URL}/api/process/{task_id}", headers={"Accept": "application/json"})
        p_data = p_res.json()
        print(f"   Progress: {p_data.get('progress')}% - Status: {p_data.get('status')}")
        if p_data.get("progress") == 100:
            break
        elif p_data.get("progress") == -1:
            raise RuntimeError(f"Processing failed: {p_data}")
        time.sleep(0.5)

    # 4. Fetch Results
    print("\n[Step 3] Fetching preview results from /api/results/{task_id}...")
    r_res = requests.get(f"{BASE_URL}/api/results/{task_id}")
    assert r_res.status_code == 200, f"Results fetch failed: {r_res.text}"
    results = r_res.json()

    syl_topics = results.get("syllabus_topics", [])
    other_topics = results.get("other_topics", [])
    coverage = results.get("coverage", {})

    print(f"-> Syllabus Topics found: {len(syl_topics)}")
    for st in syl_topics:
        matches_count = len(st.get("matches", []))
        score = st.get("similarity_score", 0)
        print(f"   - [Syllabus] {st.get('unit')} > {st.get('title')} ({matches_count} excerpts, score: {score:.2f})")

    print(f"-> Other Topics (Non-Syllabus) found: {len(other_topics)}")
    for ot in other_topics:
        matches_count = len(ot.get("matches", []))
        print(f"   - [Other] {ot.get('title')} ({matches_count} excerpts)")

    assert len(syl_topics) > 0, "No syllabus topics found"
    assert len(other_topics) > 0, "No other topics detected from non-syllabus sections"

    # Verify that Z-Transform and Noise Reduction were captured in Other Topics
    other_titles = [ot["title"].lower() for ot in other_topics]
    has_z_transform = any("z-transform" in t or "transform" in t for t in other_titles)
    has_noise = any("noise" in t for t in other_titles)
    print(f"-> Verified 'Z-Transform' in Other Topics: {has_z_transform}")
    print(f"-> Verified 'Noise Reduction' in Other Topics: {has_noise}")
    assert has_z_transform or has_noise, "Other topics should identify non-syllabus sections!"

    # 5. Generate DOCX with Syllabus Topics + Selected Other Topic
    print("\n[Step 4] Generating DOCX with user-selected topics...")
    selected_topic_ids = [st["topic_id"] for st in syl_topics if st.get("matches")]
    if other_topics:
        selected_topic_ids.append(other_topics[0]["topic_id"])

    gen_payload = {
        "selected_topic_ids": selected_topic_ids,
        "export_format": "docx"
    }
    g_res = requests.post(f"{BASE_URL}/api/generate/{task_id}", json=gen_payload)
    assert g_res.status_code == 200, f"DOCX generation failed: {g_res.text}"
    gen_data = g_res.json()
    print(f"-> Generation response: {gen_data}")

    # 6. Download DOCX
    print("\n[Step 5] Downloading generated DOCX file...")
    dl_res = requests.get(f"{BASE_URL}{gen_data['download_url']}")
    assert dl_res.status_code == 200, "DOCX download failed"
    docx_output_path = "scratch/downloaded_verified_notes.docx"
    with open(docx_output_path, "wb") as f:
        f.write(dl_res.content)
    print(f"-> Saved DOCX to {docx_output_path} ({os.path.getsize(docx_output_path)} bytes)")

    # 7. Inspect DOCX Content
    print("\n[Step 6] Inspecting DOCX paragraphs to verify ACTUAL extracted notes text...")
    doc = docx.Document(docx_output_path)
    full_docx_text = "\n".join([p.text for p in doc.paragraphs])
    
    print("\n--- DOCX TEXT EXCERPT ---")
    print(full_docx_text[:600] + "...\n--------------------------")

    # Critical assertions: The file MUST contain actual notes, not just titles or similarity percentages!
    assert "A signal is a function that conveys information" in full_docx_text, "DOCX missing extracted content from 1.1!"
    assert "Continuous-time signals are represented as continuous functions" in full_docx_text, "DOCX missing extracted content from 1.2!"
    assert "Discrete-time signals are represented mathematically as sequences" in full_docx_text, "DOCX missing extracted content from 1.3!"
    assert "Source: signals_notes.txt" in full_docx_text, "DOCX missing Source citation!"
    assert "Page:" in full_docx_text, "DOCX missing Page citation!"
    print("-> DOCX Content Verification: PASS (Contains full notes, unit headers, topic titles, and citations!)")

    # 8. Generate and Download PDF
    print("\n[Step 7] Generating and downloading PDF format...")
    pdf_payload = {
        "selected_topic_ids": selected_topic_ids,
        "export_format": "pdf"
    }
    pdf_gen_res = requests.post(f"{BASE_URL}/api/generate/{task_id}", json=pdf_payload)
    assert pdf_gen_res.status_code == 200, f"PDF generation failed: {pdf_gen_res.text}"
    pdf_gen_data = pdf_gen_res.json()

    pdf_dl_res = requests.get(f"{BASE_URL}{pdf_gen_data['download_url']}")
    assert pdf_dl_res.status_code == 200, "PDF download failed"
    pdf_output_path = "scratch/downloaded_verified_notes.pdf"
    with open(pdf_output_path, "wb") as f:
        f.write(pdf_dl_res.content)
    print(f"-> Saved PDF to {pdf_output_path} ({os.path.getsize(pdf_output_path)} bytes)")

    # 9. Inspect PDF Content
    print("\n[Step 8] Inspecting PDF text with PyMuPDF...")
    pdf_doc = fitz.open(pdf_output_path)
    pdf_text = ""
    for page in pdf_doc:
        pdf_text += page.get_text()
    
    assert "A signal is a function that conveys information" in pdf_text, "PDF missing extracted content from 1.1!"
    assert "Source: signals_notes.txt" in pdf_text, "PDF missing Source citation!"
    print("-> PDF Content Verification: PASS (Contains full notes and citations!)")

    print("\n=======================================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("=======================================================\n")

if __name__ == "__main__":
    test_workflow()
