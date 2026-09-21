# -*- coding: utf-8 -*-
"""
Full Verification: Syllabus Index vs Study Material Content Source
Creates:
1. syllabus.pdf (Index document defining 4 Units and 8 Topics)
2. study_notes.pdf (10-Page Rich Study Material containing actual explanations,
   mathematical equations, diagrams, examples, and detailed paragraphs)
Executes:
- Upload to live server
- Extraction & Semantic Matching
- Verification of Document Ingestion and Matching logs
- PDF Generation
- Re-opening generated PDF with PyMuPDF to prove that the output contains
  the real multi-page study notes, NOT just the syllabus topic names.
"""

import sys
import os
import time
import requests
import pymupdf

BASE_URL = "http://localhost:8000"
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_artifacts_rich")
os.makedirs(TEST_DIR, exist_ok=True)

def create_syllabus_pdf(path: str):
    """Creates a 1-page structured syllabus index PDF."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    
    page.insert_text((50, 50), "COURSE SYLLABUS: EC8352 SIGNALS AND SYSTEMS", fontsize=14, color=(0, 0, 0))
    
    syllabus_content = [
        "UNIT I: CLASSIFICATION OF SIGNALS AND SYSTEMS",
        "  1. Continuous and Discrete Time Signals",
        "  2. Energy and Power Signals",
        "",
        "UNIT II: ANALYSIS OF CONTINUOUS TIME SIGNALS",
        "  3. Fourier Series Representation",
        "  4. Continuous Time Fourier Transform (CTFT)",
        "",
        "UNIT III: LINEAR TIME INVARIANT CONTINUOUS SYSTEMS",
        "  5. Convolution Integral and Impulse Response",
        "  6. Transfer Function and Frequency Response",
        "",
        "UNIT IV: SAMPLING AND DISCRETE TIME SYSTEMS",
        "  7. Nyquist Sampling Theorem and Aliasing",
        "  8. Discrete Fourier Transform and FFT"
    ]
    
    y = 90
    for line in syllabus_content:
        page.insert_text((50, y), line, fontsize=10, color=(0, 0, 0))
        y += 24
        
    doc.save(path)
    doc.close()
    print(f"[CREATED] Syllabus PDF: {path}")

def create_rich_study_notes_pdf(path: str):
    """Creates a 10-page rich study material PDF containing detailed notes, formulas, and diagrams."""
    doc = pymupdf.open()
    
    page_data = [
        # Page 1
        ("Continuous and Discrete Time Signals",
         "A signal is formally defined as any physical quantity that varies with time, space, or any other independent variable and conveys information about the state of a physical system. "
         "Continuous-time signals, denoted as x(t), are defined along a continuum of time t in (-infinity, +infinity). Examples include speech signals, voltage waveforms in analog circuits, and seismic vibrations. "
         "Discrete-time signals, denoted as x[n], are defined only at discrete integer instants of time n in Z. They arise naturally through periodic sampling of continuous physical processes at uniform intervals T_s.",
         "Figure 1.1: Analog continuous waveform vs digitally sampled discrete sequence"),
         
        # Page 2
        ("Energy and Power Signals",
         "The total energy E of a continuous-time signal x(t) is defined by the infinite integral of its squared magnitude: E = integral_{-inf}^{+inf} |x(t)|^2 dt. "
         "A signal is classified as an Energy Signal if 0 < E < infinity, which strictly implies that its time-averaged power P is zero. Typical energy signals are non-periodic deterministic pulses of finite duration. "
         "Conversely, the average power P of a signal is given by P = lim_{T->inf} (1/2T) integral_{-T}^{+T} |x(t)|^2 dt. A signal is a Power Signal if 0 < P < infinity, having infinite total energy. Periodic signals like sinusoidal waves are standard power signals.",
         "Figure 1.2: Normalized power spectral density and finite energy pulse envelope"),

        # Page 3
        ("Fourier Series Representation",
         "Fourier series representation allows any periodic continuous-time signal x(t) with fundamental period T_0 and fundamental frequency omega_0 = 2*pi/T_0 to be expressed as a linear combination of harmonically related complex sinusoids: "
         "x(t) = sum_{k=-inf}^{+inf} c_k * exp(j * k * omega_0 * t). "
         "The complex Fourier coefficients c_k quantify the spectral amplitude and phase distribution at harmonic multiples k*omega_0: c_k = (1/T_0) integral_{0}^{T_0} x(t) exp(-j * k * omega_0 * t) dt. "
         "Dirichlet conditions guarantee convergence: x(t) must be absolutely integrable over one period, possess a finite number of local maxima and minima, and contain a finite number of bounded discontinuities.",
         "Figure 2.1: Line spectrum harmonics of square wave synthesis"),

        # Page 4
        ("Continuous Time Fourier Transform (CTFT)",
         "The continuous-time Fourier Transform extends frequency analysis to non-periodic energy signals by taking the limit of fundamental period T_0 -> infinity. "
         "The forward Fourier Transform is defined by the integral: X(omega) = integral_{-inf}^{+inf} x(t) exp(-j * omega * t) dt. "
         "The inverse transform synthesizes the original time-domain waveform from continuous spectral densities: x(t) = (1/2*pi) integral_{-inf}^{+inf} X(omega) exp(j * omega * t) d_omega. "
         "Key mathematical properties include linearity, time-shifting (x(t-t_0) <-> X(omega)*exp(-j*omega*t_0)), frequency shifting, duality, differentiation in time (d/dt x(t) <-> j*omega*X(omega)), and Parseval's energy conservation theorem.",
         "Figure 2.2: Continuous spectrum and phase distribution for rectangular pulse"),

        # Page 5
        ("Convolution Integral and Impulse Response",
         "A continuous-time system is Linear and Time-Invariant (LTI) if it satisfies both homogeneity, additivity, and temporal shift invariance. "
         "The output y(t) of any LTI system is completely determined by the convolution of the input signal x(t) with the unit impulse response h(t): "
         "y(t) = x(t) * h(t) = integral_{-inf}^{+inf} x(tau) * h(t - tau) d_tau. "
         "Graphical convolution involves four sequential operations: time-reversal (folding h(tau) -> h(-tau)), time-shifting to t, pointwise multiplication x(tau)*h(t-tau), and integration over all tau. "
         "A system is BIBO stable if and only if its impulse response is absolutely integrable: integral_{-inf}^{+inf} |h(t)| dt < infinity.",
         "Figure 3.1: Graphical convolution steps and overlap region integration"),

        # Page 6
        ("Transfer Function and Frequency Response",
         "The frequency response H(omega) of an LTI system is the continuous Fourier transform of its impulse response h(t): H(omega) = integral h(t) exp(-j*omega*t) dt. "
         "It relates the input spectrum X(omega) to the output spectrum Y(omega) algebraically: Y(omega) = H(omega) * X(omega). "
         "The magnitude response |H(omega)| governs frequency selective attenuation or amplification (filtering), while the phase response theta(omega) determines group delay tau_g(omega) = -d theta/d omega. "
         "In linear circuit systems described by linear constant-coefficient differential equations, H(omega) is directly obtained by substituting d/dt -> j*omega.",
         "Figure 3.2: Bode magnitude and phase plot showing cutoff frequency omega_c"),

        # Page 7
        ("Nyquist Sampling Theorem and Aliasing",
         "The Nyquist-Shannon sampling theorem states that a continuous-time bandlimited signal x(t) with highest frequency component f_max (or omega_m = 2*pi*f_max) can be uniquely and perfectly reconstructed from its discrete samples x(n*T_s) if and only if the sampling frequency f_s satisfies: "
         "f_s >= 2 * f_max (Nyquist rate). "
         "If the sampling frequency falls below the Nyquist rate (f_s < 2*f_max), spectral overlap occurs between adjacent shifted replicas of X(omega) in the frequency domain. This phenomenon is known as Aliasing, causing high-frequency components to masquerade as lower frequencies and creating irreversible distortion. "
         "To prevent aliasing in practical data acquisition systems, an analog low-pass Anti-Aliasing Filter is placed prior to the analog-to-digital converter (ADC).",
         "Figure 4.1: Frequency domain spectral replication and aliasing overlap region"),

        # Page 8
        ("Signal Reconstruction and Ideal Interpolation",
         "Perfect reconstruction of a bandlimited signal from its uniform discrete samples is achieved using the ideal Whittaker-Shannon interpolation formula: "
         "x(t) = sum_{n=-inf}^{+inf} x(n * T_s) * sinc((t - n * T_s) / T_s), where sinc(u) = sin(pi*u) / (pi*u). "
         "The ideal reconstruction filter in the frequency domain is an ideal low-pass brickwall filter with bandwidth B = f_s / 2 and gain T_s. "
         "In real-world DAC hardware, practical reconstruction utilizes Zero-Order Hold (ZOH) followed by analog smoothing reconstruction filters.",
         "Figure 4.2: Sinc function interpolation and DAC reconstruction stages"),

        # Page 9
        ("Discrete Fourier Transform and FFT",
         "The Discrete Fourier Transform (DFT) converts a finite sequence of N discrete-time samples x[n] into an equivalent N-point frequency sequence X[k]: "
         "X[k] = sum_{n=0}^{N-1} x[n] * W_N^{k*n}, where W_N = exp(-j * 2*pi / N) is the complex twiddle factor. "
         "Direct computation of an N-point DFT requires N^2 complex multiplications and N(N-1) complex additions. "
         "The Fast Fourier Transform (FFT), pioneered by Cooley and Tukey, exploits symmetry (W_N^{k+N/2} = -W_N^k) and periodicity (W_N^{k+N} = W_N^k) using Radix-2 Decimation-in-Time (DIT) or Decimation-in-Frequency (DIF) algorithms, reducing computational complexity from O(N^2) to O(N log2 N).",
         "Figure 4.3: 8-point Radix-2 DIT FFT butterfly computational graph"),

        # Page 10
        ("Comprehensive Summary of Transform Relationships",
         "Summary of transform domains: Continuous-Time Fourier Transform (CTFT) maps continuous aperiodic signals to continuous spectra. "
         "Continuous-Time Fourier Series (CTFS) maps continuous periodic signals to discrete line spectra. "
         "Discrete-Time Fourier Transform (DTFT) maps discrete aperiodic sequences to continuous periodic spectra. "
         "Discrete Fourier Transform (DFT) operates strictly on finite-length discrete sequences, yielding discrete frequency bins suitable for digital computer processing and real-time DSP hardware implementation.",
         "Figure 4.4: Inter-relationship matrix between continuous, discrete, periodic, and transform domains")
    ]
    
    for idx, (title, body_text, fig_caption) in enumerate(page_data):
        page = doc.new_page(width=612, height=792)
        p_num = idx + 1
        
        # Unit Header
        unit_idx = (idx // 3) + 1
        page.insert_text((50, 60), f"UNIT {unit_idx}: SIGNALS AND SYSTEMS LECTURE NOTES", fontsize=13, color=(0, 0, 0))
        # Topic Title
        page.insert_text((50, 85), f"{p_num}. {title}", fontsize=12, color=(0, 0, 0))
        
        # Body Paragraphs
        page.insert_textbox(pymupdf.Rect(50, 105, 560, 420), body_text, fontsize=10, color=(0, 0, 0))
        
        # Diagram
        page.draw_rect(pymupdf.Rect(50, 440, 500, 580), color=(0.2, 0.4, 0.8), fill=(0.96, 0.98, 1.0))
        page.insert_text((70, 510), f"[DIAGRAM BOX]: {fig_caption}", fontsize=10, color=(0, 0, 0))
        
        page.insert_text((50, 750), f"Page {p_num} of 10 — Detailed Lecture Material", fontsize=9, color=(0.5, 0.5, 0.5))
        
    doc.save(path)
    doc.close()
    print(f"[CREATED] 10-Page Rich Study Notes PDF: {path}")

def run_rich_verification():
    print("=" * 65)
    print("  RUNNING FULL SYLLABUS INDEX VS STUDY MATERIAL PIPELINE TEST")
    print("=" * 65)
    
    syllabus_path = os.path.join(TEST_DIR, "syllabus.pdf")
    notes_path = os.path.join(TEST_DIR, "study_notes_10p.pdf")
    
    create_syllabus_pdf(syllabus_path)
    create_rich_study_notes_pdf(notes_path)
    
    # 1. Upload both files
    files = [
        ("study_material", ("study_notes_10p.pdf", open(notes_path, "rb"), "application/pdf")),
        ("syllabus", ("syllabus.pdf", open(syllabus_path, "rb"), "application/pdf"))
    ]
    data = {
        "threshold": 0.20,
        "math_mode": True,
        "handwriting_mode": False
    }
    
    print("\n[1. UPLOAD] Uploading syllabus + 10-page study notes to server...")
    upload_resp = requests.post(f"{BASE_URL}/api/upload", files=files, data=data)
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    task_id = upload_resp.json().get("task_id")
    print(f" -> Task ID: {task_id}")
    
    # 2. Wait for processing
    print(f"\n[2. PROCESSING] Tracking progress...")
    for _ in range(40):
        status_resp = requests.get(f"{BASE_URL}/api/process/{task_id}")
        data_json = status_resp.json()
        print(f" -> {data_json.get('progress')}% : {data_json.get('status')}")
        if data_json.get("progress") >= 100:
            break
        elif data_json.get("progress") == -1:
            raise RuntimeError(f"Processing failed: {data_json.get('status')}")
        time.sleep(1)
        
    # 3. Fetch results
    results_resp = requests.get(f"{BASE_URL}/api/results/{task_id}")
    res_data = results_resp.json()
    topics = res_data.get("topics", [])
    syl_topics = res_data.get("syllabus_topics", [])
    
    print(f"\n[3. MATCHING RESULTS]")
    print(f" -> Total Syllabus Topics: {len(syl_topics)}")
    print(f" -> Total Other/Additional Topics: {len(res_data.get('other_topics', []))}")
    
    matched_chars_total = 0
    matched_pages_all = set()
    
    for t in syl_topics:
        m_count = len(t.get("matches", []))
        chars = sum(len(m.get("text", "")) for m in t.get("matches", []))
        matched_chars_total += chars
        pages = [m.get("page_number") for m in t.get("matches", [])]
        matched_pages_all.update(pages)
        print(f"    - Topic: '{t['title']}' -> {m_count} matches, {chars} chars, pages: {pages}")
        
    print(f" -> Total Matched Characters across Syllabus Topics: {matched_chars_total}")
    print(f" -> Total Pages Matched: {sorted(matched_pages_all)}")
    
    assert matched_chars_total > 1000, f"Expected thousands of matched characters, got {matched_chars_total}"
    assert len(matched_pages_all) >= 5, f"Expected multiple pages matched, got {len(matched_pages_all)}"
    
    # 4. Generate Final PDF Document
    print(f"\n[4. GENERATE PDF]")
    gen_resp = requests.post(f"{BASE_URL}/api/generate/{task_id}", json={
        "export_format": "pdf",
        "selected_topic_ids": [t["topic_id"] for t in topics]
    })
    assert gen_resp.status_code == 200, f"PDF Generation failed: {gen_resp.text}"
    print(f" -> Server Response: {gen_resp.json()}")
    
    # 5. Download and Open Generated PDF
    dl_resp = requests.get(f"{BASE_URL}/api/download/{task_id}?format=pdf")
    assert dl_resp.status_code == 200
    
    out_pdf_path = os.path.join(TEST_DIR, "final_downloaded_notes.pdf")
    with open(out_pdf_path, "wb") as f:
        f.write(dl_resp.content)
        
    print(f"\n[5. INSPECTING DOWNLOADED PDF]")
    print(f" -> File saved to: {out_pdf_path} ({len(dl_resp.content)} bytes)")
    
    # Open with PyMuPDF to verify contents
    pdf_doc = pymupdf.open(out_pdf_path)
    out_page_count = len(pdf_doc)
    
    full_output_text = ""
    for p_idx in range(out_page_count):
        p = pdf_doc.load_page(p_idx)
        p_text = p.get_text("text") or ""
        full_output_text += p_text
        print(f"   [Output Page {p_idx+1}] Chars: {len(p_text.strip())} | Preview: {p_text.strip()[:90]}...")
        
    pdf_doc.close()
    
    print("\n" + "=" * 65)
    print("  FINAL CONTENT VALIDATION REPORT")
    print("=" * 65)
    print(f"Input study material pages: 10")
    print(f"Generated PDF pages: {out_page_count}")
    print(f"Generated PDF total characters: {len(full_output_text.strip())}")
    
    # VERIFICATIONS:
    # 1. Output must NOT be only 1 page
    assert out_page_count >= 4, f"FAIL: Expected multi-page output (>=4 pages), but got {out_page_count} page(s)!"
    
    # 2. Output must contain REAL study material phrases (e.g. 'infinite integral', 'Whittaker-Shannon', 'Dirichlet conditions', 'Anti-Aliasing')
    assert "infinite integral" in full_output_text or "Whittaker-Shannon" in full_output_text or "convolution" in full_output_text.lower(), "FAIL: Real study material content missing from generated PDF!"
    
    # 3. Output character count must be substantial
    assert len(full_output_text.strip()) > 3000, f"FAIL: Generated text too low ({len(full_output_text.strip())} chars)!"
    
    print("=" * 65)
    print("  ALL VERIFICATIONS PASSED 100%! GENERATED PDF CONTAINS RICH STUDY NOTES.")
    print("=" * 65)

if __name__ == "__main__":
    run_rich_verification()
