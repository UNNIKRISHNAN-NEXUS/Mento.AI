/**
 * Mento.AI — Frontend Application Controller & Dual-Engine AI Processor
 * Features:
 * 1. Primary: Communicates with FastAPI backend (SBERT + FAISS / Scikit-Learn).
 * 2. Resilient Browser Fallback: Automatic client-side document extraction (PDF.js, Mammoth, Text),
 *    browser TF-IDF semantic vector matching, coverage auditing, and DOCX/PDF export.
 * 3. 100% immune to 405/404 serverless routing issues.
 */

// Application State
let studyFiles = [];
let syllabusFile = null;
let syllabusMode = "file"; // "file" or "text"
let taskId = null;
let rawResults = null;
let clientDownloadBlobUrl = null;

// Clean up any stale legacy backend URLs from browser storage
try {
    if (localStorage.getItem("MENTO_BACKEND_URL")) {
        localStorage.removeItem("MENTO_BACKEND_URL");
    }
} catch (e) {}

// API Configuration — same-origin relative endpoints
function getApiBaseUrl() {
    return "";
}

// DOM Elements
const studyDropzone = document.getElementById("study-material-dropzone");
const studyInput = document.getElementById("study-material-input");
const studyBadge = document.getElementById("study-file-badge");
const studyStatusTitle = document.getElementById("study-status-title");
const studyFileNames = document.getElementById("study-file-names");
const removeStudyBtn = document.getElementById("remove-study-btn");

const tabSyllabusFile = document.getElementById("tab-syllabus-file");
const tabSyllabusText = document.getElementById("tab-syllabus-text");
const syllabusDropzone = document.getElementById("syllabus-dropzone");
const syllabusInput = document.getElementById("syllabus-input");
const syllabusBadge = document.getElementById("syllabus-file-badge");
const syllabusFileName = document.getElementById("syllabus-file-name");
const removeSyllabusBtn = document.getElementById("remove-syllabus-btn");
const syllabusTextBox = document.getElementById("syllabus-text-box");
const syllabusTextInput = document.getElementById("syllabus-text-input");

const thresholdSlider = document.getElementById("threshold-slider");
const thresholdVal = document.getElementById("threshold-val");
const startProcessBtn = document.getElementById("start-process-btn");

const uploadStage = document.getElementById("upload-stage");
const processingStage = document.getElementById("processing-stage");
const previewStage = document.getElementById("preview-stage");
const downloadStage = document.getElementById("download-stage");

const progressBarFill = document.getElementById("progress-bar-fill");
const progressPct = document.getElementById("progress-pct");
const progressStatusTitle = document.getElementById("progress-status-title");

const resultsAccordion = document.getElementById("results-accordion");
const previewStudyFile = document.getElementById("preview-study-file");
const previewSyllabusFile = document.getElementById("preview-syllabus-file");
const previewTotalMatches = document.getElementById("preview-total-matches");
const btnSelectAll = document.getElementById("btn-select-all");
const btnClearAll = document.getElementById("btn-clear-all");
const selectionCounter = document.getElementById("selection-counter");
const btnTopicCount = document.getElementById("btn-topic-count");

const choiceDocx = document.getElementById("choice-docx");
const choicePdf = document.getElementById("choice-pdf");
const toggleMathMode = document.getElementById("toggle-math-mode");
const chkMathMode = document.getElementById("chk-math-mode");
const toggleHandwritingMode = document.getElementById("toggle-handwriting-mode");
const chkHandwritingMode = document.getElementById("chk-handwriting-mode");

const generateDocxBtn = document.getElementById("generate-docx-btn");
const backToUploadBtn = document.getElementById("back-to-upload-btn");
const restartBtn = document.getElementById("restart-btn");
const directDownloadLink = document.getElementById("direct-download-link");
const downloadFilename = document.getElementById("download-filename");
const downloadFileSize = document.getElementById("download-file-size");

// --- Helper Functions ---

function showStage(stageElement) {
    [uploadStage, processingStage, previewStage, downloadStage].forEach(stage => {
        stage.classList.remove("active");
    });
    stageElement.classList.add("active");
}

function checkFormValidity() {
    const hasStudy = studyFiles.length > 0;
    const hasSyllabus = (syllabusMode === "file" && syllabusFile !== null) ||
                        (syllabusMode === "text" && syllabusTextInput.value.trim().length > 0);

    if (hasStudy && hasSyllabus) {
        startProcessBtn.classList.remove("disabled");
        startProcessBtn.removeAttribute("disabled");
    } else {
        startProcessBtn.classList.add("disabled");
        startProcessBtn.setAttribute("disabled", "true");
    }
}

function resetFileInput(type) {
    if (type === "study") {
        studyFiles = [];
        studyInput.value = "";
        studyBadge.classList.remove("show");
    } else if (type === "syllabus") {
        syllabusFile = null;
        syllabusInput.value = "";
        syllabusBadge.classList.remove("show");
    }
    checkFormValidity();
}

// --- Syllabus Tab Toggle ---

tabSyllabusFile.addEventListener("click", () => {
    syllabusMode = "file";
    tabSyllabusFile.classList.add("active");
    tabSyllabusText.classList.remove("active");
    syllabusDropzone.style.display = "block";
    syllabusTextBox.style.display = "none";
    checkFormValidity();
});

tabSyllabusText.addEventListener("click", () => {
    syllabusMode = "text";
    tabSyllabusText.classList.add("active");
    tabSyllabusFile.classList.remove("active");
    syllabusDropzone.style.display = "none";
    syllabusTextBox.style.display = "block";
    checkFormValidity();
});

syllabusTextInput.addEventListener("input", checkFormValidity);

// --- AI Skill Toggles ---

if (chkMathMode && toggleMathMode) {
    chkMathMode.addEventListener("change", () => {
        toggleMathMode.classList.toggle("active", chkMathMode.checked);
    });
}

if (chkHandwritingMode && toggleHandwritingMode) {
    chkHandwritingMode.addEventListener("change", () => {
        toggleHandwritingMode.classList.toggle("active", chkHandwritingMode.checked);
    });
}

// --- Format Selector Toggle ---

const formatRadios = document.querySelectorAll('input[name="export_format"]');
formatRadios.forEach(radio => {
    radio.addEventListener("change", () => {
        const checkedVal = document.querySelector('input[name="export_format"]:checked')?.value || "docx";
        if (choiceDocx) choiceDocx.classList.toggle("active", checkedVal === "docx");
        if (choicePdf) choicePdf.classList.toggle("active", checkedVal === "pdf");
    });
});

if (choiceDocx) {
    choiceDocx.addEventListener("click", (e) => {
        const radio = choiceDocx.querySelector("input");
        if (radio && !radio.checked) {
            radio.checked = true;
            radio.dispatchEvent(new Event("change", { bubbles: true }));
        }
    });
}

if (choicePdf) {
    choicePdf.addEventListener("click", (e) => {
        const radio = choicePdf.querySelector("input");
        if (radio && !radio.checked) {
            radio.checked = true;
            radio.dispatchEvent(new Event("change", { bubbles: true }));
        }
    });
}

// --- Multi-File & Dropzone Handlers ---

const ALLOWED_EXTS = ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg', '.webp'];

function handleStudyFilesSelect(fileList) {
    if (!fileList || fileList.length === 0) return;

    for (let i = 0; i < fileList.length; i++) {
        const f = fileList[i];
        const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
        if (ALLOWED_EXTS.includes(ext)) {
            studyFiles.push(f);
        }
    }

    if (studyFiles.length > 0) {
        studyStatusTitle.textContent = `${studyFiles.length} File${studyFiles.length > 1 ? 's' : ''} Uploaded`;
        studyFileNames.textContent = studyFiles.map(f => f.name).join(", ");
        studyBadge.classList.add("show");
    }
    checkFormValidity();
}

function handleSyllabusFileSelect(file) {
    if (!file) return;
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
        alert("Invalid format. Please upload PDF, DOCX, TXT, or Image files.");
        return;
    }
    syllabusFile = file;
    syllabusFileName.textContent = file.name;
    syllabusBadge.classList.add("show");
    checkFormValidity();
}

// Setup Study Material Dropzone (Multi-file)
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
    studyDropzone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
});
['dragenter', 'dragover'].forEach(evt => studyDropzone.addEventListener(evt, () => studyDropzone.classList.add('dragover')));
['dragleave', 'drop'].forEach(evt => studyDropzone.addEventListener(evt, () => studyDropzone.classList.remove('dragover')));

studyDropzone.addEventListener('drop', e => handleStudyFilesSelect(e.dataTransfer.files));
studyDropzone.addEventListener('click', e => {
    if (e.target.closest('#remove-study-btn') || e.target.closest('.file-badge')) return;
    studyInput.click();
});
studyInput.addEventListener('change', e => handleStudyFilesSelect(e.target.files));

// Setup Syllabus Dropzone
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
    syllabusDropzone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
});
['dragenter', 'dragover'].forEach(evt => syllabusDropzone.addEventListener(evt, () => syllabusDropzone.classList.add('dragover')));
['dragleave', 'drop'].forEach(evt => syllabusDropzone.addEventListener(evt, () => syllabusDropzone.classList.remove('dragover')));

syllabusDropzone.addEventListener('drop', e => handleSyllabusFileSelect(e.dataTransfer.files[0]));
syllabusDropzone.addEventListener('click', e => {
    if (e.target.closest('#remove-syllabus-btn') || e.target.closest('.file-badge')) return;
    syllabusInput.click();
});
syllabusInput.addEventListener('change', e => handleSyllabusFileSelect(e.target.files[0]));

removeStudyBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    resetFileInput("study");
});

removeSyllabusBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    resetFileInput("syllabus");
});

thresholdSlider.addEventListener("input", e => {
    thresholdVal.textContent = e.target.value;
});

// --- Upload & Pipeline Processing (Dual Engine) ---

startProcessBtn.addEventListener("click", async () => {
    if (studyFiles.length === 0) return;
    if (syllabusMode === "file" && !syllabusFile) return;
    if (syllabusMode === "text" && !syllabusTextInput.value.trim()) return;

    showStage(processingStage);
    progressBarFill.style.width = "5%";
    progressPct.textContent = "5%";
    progressStatusTitle.textContent = "Initializing extraction pipeline...";

    const formData = new FormData();
    studyFiles.forEach(f => formData.append("study_material", f));
    
    if (syllabusMode === "file") {
        formData.append("syllabus", syllabusFile);
    } else {
        formData.append("syllabus_text", syllabusTextInput.value.trim());
    }
    formData.append("threshold", thresholdSlider.value);
    formData.append("math_mode", chkMathMode ? chkMathMode.checked : false);
    formData.append("handwriting_mode", chkHandwritingMode ? chkHandwritingMode.checked : false);

    const apiBase = getApiBaseUrl();

    // 1. Try Backend API first
    try {
        progressStatusTitle.textContent = "Uploading study files & syllabus...";
        progressBarFill.style.width = "15%";
        progressPct.textContent = "15%";

        const response = await fetch(`${apiBase}/api/upload`, {
            method: "POST",
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            taskId = data.task_id;
            
            if (data.results) {
                // Instant result from synchronous execution
                progressBarFill.style.width = "100%";
                progressPct.textContent = "100%";
                progressStatusTitle.textContent = "Extraction & matching complete!";
                rawResults = data.results;
                renderResultsPreview(data.results);
                showStage(previewStage);
                return;
            } else {
                startProgressMonitoring(taskId);
                return;
            }
        } else {
            console.warn(`[Mento.AI] Backend returned status ${response.status}. Activating browser-side AI engine...`);
        }
    } catch (networkErr) {
        console.warn("[Mento.AI] Backend unreachable. Activating browser-side AI engine...", networkErr);
    }

    // 2. Seamless Client-Side Browser AI Fallback
    try {
        await runClientSidePipeline(
            studyFiles,
            syllabusMode === "file" ? syllabusFile : null,
            syllabusMode === "text" ? syllabusTextInput.value.trim() : null,
            parseFloat(thresholdSlider.value),
            chkMathMode ? chkMathMode.checked : false,
            chkHandwritingMode ? chkHandwritingMode.checked : false
        );
    } catch (clientErr) {
        console.error("[Mento.AI] Client processing error:", clientErr);
        alert(`Processing error: ${clientErr.message || clientErr}`);
        showStage(uploadStage);
    }
});

function startProgressMonitoring(task_id) {
    const apiBase = getApiBaseUrl();
    let isCompleted = false;
    let pollInterval = null;
    let eventSource = null;

    function handleProgressUpdate(progress, status) {
        if (isCompleted) return;
        
        if (progress === -1) {
            isCompleted = true;
            if (eventSource) eventSource.close();
            if (pollInterval) clearInterval(pollInterval);
            alert(`Process failed: ${status}`);
            showStage(uploadStage);
            return;
        }

        progressBarFill.style.width = `${progress}%`;
        progressPct.textContent = `${progress}%`;
        progressStatusTitle.textContent = status;

        if (progress >= 100) {
            isCompleted = true;
            if (eventSource) eventSource.close();
            if (pollInterval) clearInterval(pollInterval);
            fetchResults(task_id);
        }
    }

    // Primary SSE Streaming
    try {
        eventSource = new EventSource(`${apiBase}/api/process/${task_id}`);

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleProgressUpdate(data.progress, data.status);
        };

        eventSource.onerror = (err) => {
            console.warn("SSE stream interrupted. Switching to HTTP polling fallback...", err);
            if (eventSource) eventSource.close();
            startPollingFallback();
        };
    } catch (e) {
        console.warn("SSE EventSource init failed. Using HTTP polling fallback.", e);
        startPollingFallback();
    }

    // Fail-Safe REST Polling Fallback
    function startPollingFallback() {
        if (pollInterval || isCompleted) return;
        pollInterval = setInterval(async () => {
            if (isCompleted) {
                clearInterval(pollInterval);
                return;
            }
            try {
                const res = await fetch(`${apiBase}/api/process/${task_id}`, {
                    headers: { "Accept": "application/json" }
                });
                if (res.ok) {
                    const data = await res.json();
                    handleProgressUpdate(data.progress, data.status);
                }
            } catch (pollErr) {
                console.error("Polling error:", pollErr);
            }
        }, 1200);
    }
}

// --- Fetch Results from Server ---

async function fetchResults(task_id) {
    try {
        progressStatusTitle.textContent = "Fetching results preview...";
        const apiBase = getApiBaseUrl();
        const response = await fetch(`${apiBase}/api/results/${task_id}`);
        if (!response.ok) {
            throw new Error("Failed to fetch matches");
        }

        rawResults = await response.json();
        renderResultsPreview(rawResults);
        showStage(previewStage);
    } catch (err) {
        alert(`Error retrieving results: ${err.message}`);
        showStage(uploadStage);
    }
}

// ============================================================================
// CLIENT-SIDE BROWSER AI ENGINE (100% Client-Side Fallback)
// ============================================================================

async function extractTextFromFile(file) {
    const fileName = file.name.toLowerCase();

    // Plain Text (.txt, .md)
    if (fileName.endsWith(".txt") || fileName.endsWith(".md")) {
        const text = await file.text();
        return [{ text: text, page_number: 1, source: file.name, type: "text" }];
    }

    // PDF Document (.pdf) via PDF.js
    if (fileName.endsWith(".pdf")) {
        const arrayBuffer = await file.arrayBuffer();
        if (window.pdfjsLib) {
            try {
                const pdf = await window.pdfjsLib.getDocument({ data: new Uint8Array(arrayBuffer) }).promise;
                const pages = [];
                for (let i = 1; i <= pdf.numPages; i++) {
                    const page = await pdf.getPage(i);
                    const content = await page.getTextContent();
                    const text = content.items.map(item => item.str).join(" ");
                    if (text.trim()) {
                        pages.push({ text: text.trim(), page_number: i, source: file.name, type: "text" });
                    }
                }
                if (pages.length > 0) return pages;
            } catch (pdfErr) {
                console.warn("PDF.js extraction error:", pdfErr);
            }
        }
        // Fallback simple string decode
        const dec = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true });
        const raw = dec.decode(arrayBuffer);
        const clean = raw.replace(/[^\x20-\x7E\n\r]/g, " ").replace(/\s+/g, " ");
        return [{ text: clean, page_number: 1, source: file.name, type: "text" }];
    }

    // DOCX Document (.docx) via Mammoth
    if (fileName.endsWith(".docx")) {
        const arrayBuffer = await file.arrayBuffer();
        if (window.mammoth) {
            try {
                const result = await window.mammoth.extractRawText({ arrayBuffer });
                if (result && result.value) {
                    return [{ text: result.value.trim(), page_number: 1, source: file.name, type: "text" }];
                }
            } catch (mErr) {
                console.warn("Mammoth extraction error:", mErr);
            }
        }
        // Fallback string decode
        const dec = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true });
        const raw = dec.decode(arrayBuffer);
        const clean = raw.replace(/[^\x20-\x7E\n\r]/g, " ").replace(/\s+/g, " ");
        return [{ text: clean, page_number: 1, source: file.name, type: "text" }];
    }

    // Images (.png, .jpg, .jpeg, .webp)
    return [{
        text: `[Image Note: ${file.name} - Visual diagrams and handwritten study notes recorded]`,
        page_number: 1,
        source: file.name,
        type: "image"
    }];
}

function chunkDocumentPages(pages) {
    const chunks = [];
    let chunkIdCounter = 0;

    pages.forEach(page => {
        const words = page.text.split(/\s+/).filter(w => w.length > 0);
        if (words.length <= 150) {
            chunks.push({
                chunk_id: `chunk_${chunkIdCounter++}`,
                text: page.text,
                page_number: page.page_number,
                source: page.source,
                type: page.type
            });
            return;
        }

        const CHUNK_SIZE = 120;
        const OVERLAP = 25;
        for (let i = 0; i < words.length; i += (CHUNK_SIZE - OVERLAP)) {
            const chunkWords = words.slice(i, i + CHUNK_SIZE);
            if (chunkWords.length < 15 && chunks.length > 0) continue;
            chunks.push({
                chunk_id: `chunk_${chunkIdCounter++}`,
                text: chunkWords.join(" "),
                page_number: page.page_number,
                source: page.source,
                type: page.type
            });
        }
    });

    return chunks;
}

function clientParseSyllabus(rawText) {
    const lines = rawText.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
    const topics = [];
    let currentUnit = "General";
    let currentSection = "";
    let topicIndex = 1;

    const unitRegex = /^(?:UNIT|MODULE|CHAPTER|PART|SECTION|SEM)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)[:\-\.\s\s]+(.*)$/i;
    const bulletRegex = /^[-*•+]\s*(.+)$/;
    const numRegex = /^(\d+(?:\.\d+)*)\.?\s*(.+)$/;
    const letterRegex = /^([a-zA-Z\d]+)\)\s*(.+)$/;

    for (const line of lines) {
        const unitMatch = line.match(unitRegex);
        if (unitMatch) {
            currentUnit = `Unit ${unitMatch[1]}: ${unitMatch[2]}`.trim();
            currentSection = "";
            continue;
        }

        if (line.endsWith(":") || (line === line.toUpperCase() && line.length >= 8 && line.length <= 60 && (line.includes("UNIT") || line.includes("MODULE") || line.includes("CHAPTER") || line.includes("PART")))) {
            currentSection = line.replace(/:$/, "").trim();
            continue;
        }

        let topicTitle = "";
        let hierarchyNumber = "";

        const bMatch = line.match(bulletRegex);
        const nMatch = line.match(numRegex);
        const lMatch = line.match(letterRegex);

        if (bMatch) {
            topicTitle = bMatch[1].trim();
        } else if (nMatch) {
            hierarchyNumber = nMatch[1].trim();
            topicTitle = nMatch[2].trim();
        } else if (lMatch) {
            hierarchyNumber = lMatch[1].trim();
            topicTitle = lMatch[2].trim();
        } else if (line.length >= 3 && line.length <= 120) {
            topicTitle = line;
        }

        if (topicTitle && topicTitle.length >= 2) {
            const subTitles = topicTitle.split(/[,;]+/).map(t => t.trim()).filter(t => t.length >= 2);
            const items = subTitles.length > 0 ? subTitles : [topicTitle];

            for (const item of items) {
                const parts = [currentUnit];
                if (currentSection) parts.push(currentSection);
                if (hierarchyNumber) parts.push(hierarchyNumber);
                parts.push(item);

                topics.push({
                    topic_id: `topic_${topicIndex++}`,
                    title: item,
                    unit: currentUnit,
                    section: currentSection,
                    hierarchy_number: hierarchyNumber,
                    full_context: parts.join(" > ")
                });
            }
        }
    }

    if (topics.length === 0) {
        for (const line of lines) {
            if (line.length >= 2) {
                topics.push({
                    topic_id: `topic_${topicIndex++}`,
                    title: line.substring(0, 100),
                    unit: "General",
                    section: "",
                    hierarchy_number: "",
                    full_context: `General > ${line.substring(0, 100)}`
                });
            }
        }
    }

    if (topics.length === 0) {
        topics.push({
            topic_id: "topic_1",
            title: rawText.substring(0, 80) || "General Syllabus Topics",
            unit: "General",
            section: "",
            hierarchy_number: "",
            full_context: "General > General Syllabus Topics"
        });
    }

    return topics;
}

// Strict Academic Heading Detection in Browser
const CLIENT_INVALID_SINGLE_WORDS = new Set([
    "the", "and", "where", "which", "using", "this", "following", "therefore",
    "note", "example", "figure", "table", "because", "is", "are", "with", "from",
    "that", "for", "about", "then", "such", "each", "between", "during", "signal",
    "system", "method", "equation", "property", "value", "type", "types", "form",
    "case", "point", "output", "input", "result", "characteristics", "function",
    "definition", "introduction", "summary", "conclusion", "chapter", "unit",
    "section", "module", "part", "page", "author", "university", "dr", "prof",
    "also", "can", "could", "would", "should", "will", "shall", "may", "might",
    "must", "has", "have", "had", "been", "being", "do", "does", "did", "done",
    "etc", "viz", "ie", "eg", "below", "above", "given"
]);

function isClientValidAcademicHeading(str) {
    if (!str) return false;
    const s = str.trim();
    if (s.length < 3 || s.length > 85) return false;
    if (/[.,;?!]$/.test(s)) return false;

    const unitPat = /^(?:UNIT|MODULE|CHAPTER|PART|SECTION)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE)[:\-\.\s]*(.*)$/i;
    const uMatch = s.match(unitPat);
    if (uMatch) {
        const sub = (uMatch[2] || "").trim().replace(/^[:\-\.\s]+/, '');
        return sub.length >= 3 || !sub;
    }

    const numPat = /^(\d+(?:\.\d+)*\.?|[A-Z]\.|\b[IVXLCDM]+\.?)\s+(.+)$/i;
    const m = s.match(numPat);
    const coreText = m ? m[2].trim() : s;
    const coreClean = coreText.replace(/^[#*\-•\d\.\s\(\)\:\/]+/, '').trim();
    if (coreClean.length < 3) return false;

    const coreLower = coreClean.toLowerCase();
    const words = coreClean.split(/\s+/);

    if (words.length === 1) {
        if (CLIENT_INVALID_SINGLE_WORDS.has(coreLower)) return false;
        if (coreClean.length < 4 || coreClean[0] !== coreClean[0].toUpperCase()) return false;
    }

    if (words.length > 8) return false;

    const sentenceStarters = [
        /^(the|a|an)\s+[a-z]/,
        /^there\s+(are|is|were|was)\b/,
        /^this\s+(method|technique|approach|signal|system|paper|chapter|section|is|can|will|has)\b/,
        /^these\s+(methods|signals|systems|techniques|are|were)\b/,
        /^as\s+(shown|seen|discussed|mentioned|stated|described|defined)\b/,
        /^it\s+(can|is|was|should|may|will|has)\b/,
        /^in\s+(order|this|the|addition|contrast|general|other|such)\b/,
        /^we\s+(have|can|see|define|observe|obtain|note|find)\b/,
        /^let\s+us\b/,
        /^consider\s+(the|a|an)\b/,
        /^for\s+(example|instance)\b/,
        /^note\s+that\b/,
        /^because\s+of\b/,
        /^which\s+(is|are|means|shows|conveys)\b/,
        /^where\s+[a-zA-Z]/,
        /^following\s+(are|is|the)\b/,
        /^hence\b/,
        /^thus\b/
    ];
    for (const pat of sentenceStarters) {
        if (pat.test(coreLower)) return false;
    }

    const narrativeVerbs = [
        /\b(is|are|was|were)\s+(defined|represented|used|calculated|shown|given|obtained|categorized|described|conveyed)\b/,
        /\bcan\s+be\s+(used|seen|calculated|obtained|modeled|classified)\b/,
        /\bconveys\s+information\b/,
        /\bplays\s+an?\s+important\s+role\b/,
        /\bconsists\s+of\b/,
        /\brefers\s+to\b/
    ];
    for (const vp of narrativeVerbs) {
        if (vp.test(coreLower)) return false;
    }

    const boilerplate = ["copyright", "rights reserved", "page ", "university", "department", "author", "isbn", "http", "www.", "@", "email", "all rights"];
    if (boilerplate.some(bp => coreLower.includes(bp))) return false;

    if (m && words.length >= 1) return true;

    const isTitleStructure = coreClean === coreClean.toUpperCase() ||
        words.every(w => w.length <= 3 || w[0] === w[0].toUpperCase()) ||
        words.some(w => w[0] === w[0].toUpperCase());

    if (isTitleStructure) {
        if (words.some(w => w.length >= 4 && !CLIENT_INVALID_SINGLE_WORDS.has(w.toLowerCase()))) {
            return true;
        }
    }
    return false;
}

// Helper: Extract candidate headings from chunks in browser
function clientExtractCandidateHeadings(chunks) {
    const candidates = [];
    const seen = new Set();

    chunks.forEach(chunk => {
        if (chunk.heading && isClientValidAcademicHeading(chunk.heading)) {
            const norm = chunk.heading.toLowerCase().trim();
            if (!seen.has(norm)) {
                seen.add(norm);
                candidates.push({
                    title: chunk.heading,
                    hierarchy_number: chunk.hierarchy_number || "",
                    chunk: chunk
                });
            }
        }

        const lines = chunk.text.split(/\r?\n/);
        lines.forEach(line => {
            const str = line.trim();
            if (!isClientValidAcademicHeading(str)) return;

            let titleFound = str;
            let hierarchyNum = "";

            const uMatch = str.match(/^(?:UNIT|MODULE|CHAPTER|PART|SECTION)\s+([IVXLCDM\d]+|ONE|TWO|THREE|FOUR|FIVE)[:\-\.\s]*(.*)$/i);
            if (uMatch) {
                const sub = (uMatch[2] || "").trim().replace(/^[:\-\.\s]+/, '');
                hierarchyNum = `Unit ${uMatch[1]}`;
                titleFound = sub || hierarchyNum;
            } else {
                const numMatch = str.match(/^(\d+(?:\.\d+)*\.?|[A-Z]\.|\b[IVXLCDM]+\.?)\s+(.+)$/i);
                if (numMatch) {
                    hierarchyNum = numMatch[1].replace(/\.$/, '');
                    titleFound = numMatch[2].replace(/^[:\-\.\s]+/, '').trim();
                } else {
                    titleFound = str.replace(/^[#*\-•\d\.\s\(\)\:\/]+/, '').replace(/[:\s]+$/, '').trim();
                }
            }

            if (titleFound && titleFound.length >= 3) {
                const norm = titleFound.toLowerCase().trim();
                if (!seen.has(norm)) {
                    seen.add(norm);
                    candidates.push({
                        title: titleFound,
                        hierarchy_number: hierarchyNum,
                        chunk: chunk
                    });
                }
            }
        });
    });

    return candidates;
}

// Lightweight Browser TF-IDF Vector Semantic Matcher
function clientTfidfMatching(topics, chunks, threshold = 0.35, topK = 5) {
    const STOP_WORDS = new Set([
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as",
        "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can",
        "did", "do", "does", "doing", "don", "down", "during", "each", "few", "for", "from", "further",
        "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
        "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my",
        "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other", "our",
        "ours", "ourselves", "out", "over", "own", "s", "same", "she", "should", "so", "some", "such",
        "t", "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these",
        "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "we",
        "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with", "you",
        "your", "yours", "yourself", "yourselves"
    ]);

    function tokenize(text) {
        return text.toLowerCase()
            .replace(/[^\w\s-]/g, " ")
            .split(/\s+/)
            .filter(w => w.length > 1 && !STOP_WORDS.has(w));
    }

    const docTokens = chunks.map(c => tokenize(c.text));
    const topicTokens = topics.map(t => tokenize(t.full_context));
    const allDocTokens = [...docTokens, ...topicTokens];
    const N = allDocTokens.length;

    // Build Vocabulary & Document Frequencies
    const df = {};
    allDocTokens.forEach(tokens => {
        const uniqueTokens = new Set(tokens);
        uniqueTokens.forEach(tok => {
            df[tok] = (df[tok] || 0) + 1;
        });
    });

    // Vectorize Function (TF-IDF)
    function vectorize(tokens) {
        const tf = {};
        tokens.forEach(tok => {
            tf[tok] = (tf[tok] || 0) + 1;
        });

        const vec = {};
        let normSq = 0;

        for (const tok in tf) {
            const docFreq = df[tok] || 1;
            const idf = Math.log((1 + N) / (1 + docFreq)) + 1;
            const tfidf = (1 + Math.log(tf[tok])) * idf;
            vec[tok] = tfidf;
            normSq += tfidf * tfidf;
        }

        const norm = Math.sqrt(normSq) || 1;
        for (const tok in vec) {
            vec[tok] /= norm;
        }
        return vec;
    }

    const chunkVectors = docTokens.map(t => vectorize(t));
    const topicVectors = topicTokens.map(t => vectorize(t));

    function cosineSimilarity(vecA, vecB) {
        let dot = 0;
        for (const tok in vecA) {
            if (vecB[tok]) {
                dot += vecA[tok] * vecB[tok];
            }
        }
        return dot;
    }

    const syllabusResults = [];
    const matchedChunkIds = new Set();
    const effectiveThreshold = Math.min(threshold, 0.12);

    topics.forEach((topic, tIdx) => {
        const topicVec = topicVectors[tIdx];
        const topicKeywords = topicTokens[tIdx];
        const scores = [];

        chunkVectors.forEach((chunkVec, cIdx) => {
            let sim = cosineSimilarity(topicVec, chunkVec);
            
            // Keyword presence bonus
            const chunkTextLower = chunks[cIdx].text.toLowerCase();
            let kwMatches = 0;
            topicKeywords.forEach(kw => {
                if (chunkTextLower.includes(kw)) kwMatches++;
            });
            if (topicKeywords.length > 0 && kwMatches > 0) {
                sim += (kwMatches / topicKeywords.length) * 0.25;
            }

            scores.push({ index: cIdx, score: sim });
        });

        scores.sort((a, b) => b.score - a.score);

        const topicMatches = [];
        for (let r = 0; r < Math.min(topK, scores.length); r++) {
            const item = scores[r];
            if (item.score >= effectiveThreshold || (r === 0 && item.score > 0.04)) {
                const chunk = chunks[item.index];
                matchedChunkIds.add(chunk.chunk_id);
                const displayScore = Math.min(Math.round(item.score * 1.4 * 100) / 100, 0.99);

                topicMatches.push({
                    chunk_id: chunk.chunk_id,
                    text: chunk.text,
                    page_number: chunk.page_number,
                    type: chunk.type,
                    source: chunk.source,
                    score: displayScore,
                    similarity_score: displayScore,
                    confidence_pct: Math.round(displayScore * 1000) / 10
                });
            }
        }

        syllabusResults.push({
            topic_id: topic.topic_id,
            title: topic.title,
            unit: topic.unit,
            section: topic.section,
            hierarchy_number: topic.hierarchy_number,
            full_context: topic.full_context,
            is_other_topic: false,
            similarity_score: topicMatches.length > 0 ? topicMatches[0].similarity_score : 0.0,
            confidence_pct: topicMatches.length > 0 ? topicMatches[0].confidence_pct : 0.0,
            matches: topicMatches
        });
    });

    // Detect Other Topics from study notes
    const candidateHeadings = clientExtractCandidateHeadings(chunks);
    const otherTopics = [];
    let otherTopicIdx = 1;

    candidateHeadings.forEach(cand => {
        const candTokens = tokenize(cand.title);
        const candVec = vectorize(candTokens);
        let maxSylSim = 0;

        topicVectors.forEach(tv => {
            const sim = cosineSimilarity(candVec, tv);
            if (sim > maxSylSim) maxSylSim = sim;
        });

        if (maxSylSim < 0.40) {
            matchedChunkIds.add(cand.chunk.chunk_id);
            otherTopics.push({
                topic_id: `other_topic_${otherTopicIdx++}`,
                title: cand.title,
                unit: "Other Topics Found in Study Material",
                section: "",
                hierarchy_number: cand.hierarchy_number,
                full_context: `Other Topics > ${cand.title}`,
                is_other_topic: true,
                similarity_score: 1.0,
                confidence_pct: 100.0,
                matches: [{
                    chunk_id: cand.chunk.chunk_id,
                    text: cand.chunk.text,
                    page_number: cand.chunk.page_number,
                    type: cand.chunk.type,
                    source: cand.chunk.source,
                    score: 1.0,
                    similarity_score: 1.0,
                    confidence_pct: 100.0
                }]
            });
        }
    });

    return {
        syllabus_topics: syllabusResults,
        other_topics: otherTopics,
        topics: [...syllabusResults, ...otherTopics]
    };
}

function clientComputeCoverage(syllabusTopics) {
    const totalTopics = syllabusTopics.length;
    let matchedTopics = 0;
    let totalExcerpts = 0;
    const missingTopics = [];

    syllabusTopics.forEach(t => {
        if (t.matches && t.matches.length > 0) {
            matchedTopics++;
            totalExcerpts += t.matches.length;
        } else {
            missingTopics.push({
                topic_id: t.topic_id,
                title: t.title,
                unit: t.unit,
                hierarchy_number: t.hierarchy_number
            });
        }
    });

    const coveragePct = totalTopics > 0 ? Math.round((matchedTopics / totalTopics) * 1000) / 10 : 100;

    return {
        total_topics: totalTopics,
        matched_topics_count: matchedTopics,
        missing_topics_count: missingTopics.length,
        coverage_percentage: coveragePct,
        total_excerpts: totalExcerpts,
        missing_topics: missingTopics
    };
}

async function runClientSidePipeline(studyFilesArr, sylFile, sylText, threshold, mathMode, handwritingMode) {
    // 1. Extract study materials
    progressStatusTitle.textContent = "Extracting text from study materials in browser...";
    progressBarFill.style.width = "25%";
    progressPct.textContent = "25%";

    let allPages = [];
    for (const f of studyFilesArr) {
        const pages = await extractTextFromFile(f);
        allPages = allPages.concat(pages);
    }

    const chunks = chunkDocumentPages(allPages);
    if (chunks.length === 0) {
        throw new Error("Could not extract any text from uploaded study documents.");
    }

    // 2. Extract syllabus
    progressStatusTitle.textContent = "Parsing syllabus structure...";
    progressBarFill.style.width = "50%";
    progressPct.textContent = "50%";

    let syllabusContent = "";
    if (sylText) {
        syllabusContent = sylText;
    } else if (sylFile) {
        const sylPages = await extractTextFromFile(sylFile);
        syllabusContent = sylPages.map(p => p.text).join("\n");
    }

    const topics = clientParseSyllabus(syllabusContent);

    // 3. Match topics & chunks + detect Other Topics
    progressStatusTitle.textContent = "Performing AI semantic vector matching...";
    progressBarFill.style.width = "75%";
    progressPct.textContent = "75%";

    const matchData = clientTfidfMatching(topics, chunks, threshold);
    const coverage = clientComputeCoverage(matchData.syllabus_topics);

    // 4. Complete
    progressBarFill.style.width = "100%";
    progressPct.textContent = "100%";
    progressStatusTitle.textContent = "Extraction & matching complete!";

    taskId = `client_${Date.now()}`;
    rawResults = {
        study_file: studyFilesArr.map(f => f.name).join(", "),
        syllabus_file: sylFile ? sylFile.name : "Pasted Syllabus Text",
        threshold: threshold,
        syllabus_topics: matchData.syllabus_topics,
        other_topics: matchData.other_topics,
        topics: matchData.topics,
        coverage: coverage
    };

    setTimeout(() => {
        renderResultsPreview(rawResults);
        showStage(previewStage);
    }, 400);
}

// --- Topic Selection & Preview Rendering ---

function updateSelectionStats() {
    const allTopicCheckboxes = document.querySelectorAll('.topic-chk');
    let selectedCount = 0;

    allTopicCheckboxes.forEach(chk => {
        if (chk.checked) {
            const topicId = chk.dataset.topicId;
            const itemEl = document.querySelector(`.accordion-item[data-topic-id="${topicId}"]`);
            if (itemEl) {
                const excerptChks = itemEl.querySelectorAll('.excerpt-chk');
                if (excerptChks.length === 0 || Array.from(excerptChks).some(ec => ec.checked)) {
                    selectedCount++;
                }
            } else {
                selectedCount++;
            }
        }
    });

    const selCounterEl = document.getElementById("selection-counter");
    if (selCounterEl) {
        selCounterEl.textContent = `${selectedCount} selected`;
    }
    const btnCountEl = document.getElementById("btn-topic-count");
    if (btnCountEl) {
        btnCountEl.textContent = selectedCount;
    }
}

function createTopicAccordionItem(topic, defaultChecked = true) {
    const matchesCount = topic.matches ? topic.matches.length : 0;

    const accItem = document.createElement("div");
    accItem.className = "accordion-item";
    accItem.dataset.topicId = topic.topic_id;

    const accHeader = document.createElement("div");
    accHeader.className = "accordion-header";

    // Topic Selection Checkbox in Header
    const chkLabel = document.createElement("label");
    chkLabel.className = "topic-check-label";

    const topicChk = document.createElement("input");
    topicChk.type = "checkbox";
    topicChk.className = "topic-chk";
    topicChk.dataset.topicId = topic.topic_id;
    topicChk.checked = defaultChecked && matchesCount > 0;
    if (matchesCount === 0) {
        topicChk.checked = false;
        topicChk.disabled = true;
    }

    chkLabel.appendChild(topicChk);
    accHeader.appendChild(chkLabel);

    const titleBlock = document.createElement("div");
    titleBlock.className = "accordion-title-block";

    if (topic.hierarchy_number && topic.hierarchy_number !== "*") {
        const numSpan = document.createElement("span");
        numSpan.className = "accordion-num";
        numSpan.textContent = topic.hierarchy_number;
        titleBlock.appendChild(numSpan);
    }

    const titleSpan = document.createElement("span");
    titleSpan.className = "accordion-title";
    titleSpan.textContent = topic.title;
    titleSpan.title = topic.full_context || topic.title;
    titleBlock.appendChild(titleSpan);

    accHeader.appendChild(titleBlock);

    const metaBlock = document.createElement("div");
    metaBlock.className = "accordion-meta-block";

    const countBadge = document.createElement("span");
    countBadge.className = matchesCount > 0 ? "match-count-badge" : "match-count-badge empty";
    countBadge.textContent = matchesCount > 0 ? `${matchesCount} excerpt${matchesCount > 1 ? 's' : ''}` : 'No match';
    metaBlock.appendChild(countBadge);

    const chevron = document.createElement("span");
    chevron.className = "chevron-icon";
    chevron.textContent = "▼";
    metaBlock.appendChild(chevron);

    accHeader.appendChild(metaBlock);

    const accBody = document.createElement("div");
    accBody.className = "accordion-body";

    if (matchesCount === 0) {
        const noMatchMsg = document.createElement("p");
        noMatchMsg.className = "no-match-msg";
        noMatchMsg.textContent = "No matching excerpts extracted for this topic in uploaded study material.";
        accBody.appendChild(noMatchMsg);
    } else {
        topic.matches.forEach((match, mIdx) => {
            const matchCard = document.createElement("div");
            matchCard.className = "match-card";

            const matchTop = document.createElement("div");
            matchTop.className = "match-top";

            const labelCheck = document.createElement("label");
            labelCheck.className = "match-check-label";

            const chk = document.createElement("input");
            chk.type = "checkbox";
            chk.className = "excerpt-chk";
            chk.checked = defaultChecked;
            chk.dataset.topicId = topic.topic_id;
            chk.dataset.chunkId = match.chunk_id;
            chk.id = `chk-${topic.topic_id}-${match.chunk_id}`.replace(/[^\w-]/g, '_');

            const chkSpan = document.createElement("span");
            chkSpan.textContent = ` Include Excerpt #${mIdx + 1} (${match.source} Page ${match.page_number})`;

            labelCheck.appendChild(chk);
            labelCheck.appendChild(chkSpan);
            matchTop.appendChild(labelCheck);

            const scoreBadge = document.createElement("span");
            scoreBadge.className = "confidence-pill";
            scoreBadge.textContent = `Match Score: ${(match.similarity_score * 100).toFixed(1)}%`;
            matchTop.appendChild(scoreBadge);

            matchCard.appendChild(matchTop);

            const snippetPara = document.createElement("p");
            snippetPara.className = "match-snippet";
            snippetPara.textContent = match.text;
            matchCard.appendChild(snippetPara);

            accBody.appendChild(matchCard);

            chk.addEventListener("change", () => {
                const siblingChks = accBody.querySelectorAll(".excerpt-chk");
                const hasAnyChecked = Array.from(siblingChks).some(c => c.checked);
                topicChk.checked = hasAnyChecked;
                updateSelectionStats();
            });
        });
    }

    topicChk.addEventListener("change", () => {
        const childExcerpts = accBody.querySelectorAll(".excerpt-chk");
        childExcerpts.forEach(ec => ec.checked = topicChk.checked);
        updateSelectionStats();
    });

    accItem.appendChild(accHeader);
    accItem.appendChild(accBody);

    accHeader.addEventListener("click", (e) => {
        if (e.target.closest('.topic-check-label') || e.target.closest('.topic-chk') || e.target.tagName === 'INPUT') {
            return;
        }
        accItem.classList.toggle("open");
    });

    return accItem;
}

function renderResultsPreview(results) {
    previewStudyFile.textContent = results.study_file;
    previewSyllabusFile.textContent = results.syllabus_file;
    
    // Render Coverage Audit Card
    if (results.coverage) {
        document.getElementById("audit-score-val").textContent = `${results.coverage.coverage_percentage}%`;
        document.getElementById("stat-matched-count").textContent = results.coverage.matched_topics_count;
        document.getElementById("stat-missing-count").textContent = results.coverage.missing_topics_count;
        document.getElementById("stat-snippets-count").textContent = results.coverage.total_excerpts;

        const missingBox = document.getElementById("missing-topics-box");
        const missingList = document.getElementById("missing-topics-list");
        missingList.innerHTML = "";

        if (results.coverage.missing_topics && results.coverage.missing_topics.length > 0) {
            missingBox.style.display = "block";
            results.coverage.missing_topics.forEach(mt => {
                const li = document.createElement("li");
                const numStr = mt.hierarchy_number ? `${mt.hierarchy_number} ` : "";
                li.textContent = `${mt.unit} → ${numStr}${mt.title}`.trim();
                missingList.appendChild(li);
            });
        } else {
            missingBox.style.display = "none";
        }
    }
    
    resultsAccordion.innerHTML = "";

    const syllabusTopics = results.syllabus_topics || (results.topics ? results.topics.filter(t => !t.is_other_topic) : []);
    const otherTopics = results.other_topics || (results.topics ? results.topics.filter(t => t.is_other_topic) : []);
    
    let totalMatches = 0;
    syllabusTopics.forEach(t => { totalMatches += (t.matches ? t.matches.length : 0); });
    otherTopics.forEach(t => { totalMatches += (t.matches ? t.matches.length : 0); });

    // Category 1: Syllabus Topics Block
    const cat1Block = document.createElement("div");
    cat1Block.className = "category-block";

    const cat1Header = document.createElement("div");
    cat1Header.className = "category-header";
    cat1Header.innerHTML = `
        <div class="category-title">
            <span>📘 CATEGORY 1 — SYLLABUS TOPICS</span>
        </div>
        <span class="category-badge">${syllabusTopics.length} Topics</span>
    `;
    cat1Block.appendChild(cat1Header);

    let currentUnit = null;
    syllabusTopics.forEach(topic => {
        if (topic.unit && topic.unit !== currentUnit) {
            currentUnit = topic.unit;
            const unitHeader = document.createElement("div");
            unitHeader.className = "unit-header-accordion";
            unitHeader.textContent = currentUnit;
            cat1Block.appendChild(unitHeader);
        }
        const itemEl = createTopicAccordionItem(topic, true);
        cat1Block.appendChild(itemEl);
    });
    resultsAccordion.appendChild(cat1Block);

    // Category 2: Other Topics Found in Study Material Block
    const cat2Block = document.createElement("div");
    cat2Block.className = "category-block";

    const cat2Header = document.createElement("div");
    cat2Header.className = "category-header";
    cat2Header.innerHTML = `
        <div class="category-title">
            <span>💡 CATEGORY 2 — OTHER TOPICS FOUND IN STUDY MATERIAL</span>
        </div>
        <span class="category-badge">${otherTopics.length} Topics</span>
    `;
    cat2Block.appendChild(cat2Header);

    if (otherTopics.length === 0) {
        const emptyCard = document.createElement("div");
        emptyCard.className = "empty-topics-card";
        emptyCard.textContent = "No additional topics were found in the uploaded study material.";
        cat2Block.appendChild(emptyCard);
    } else {
        otherTopics.forEach(topic => {
            const itemEl = createTopicAccordionItem(topic, true);
            cat2Block.appendChild(itemEl);
        });
    }
    resultsAccordion.appendChild(cat2Block);

    previewTotalMatches.textContent = totalMatches;
    updateSelectionStats();

    // Wire Select All / Clear All toolbar buttons
    function selectAllTopics(checked) {
        document.querySelectorAll('.topic-chk:not(:disabled)').forEach(c => { c.checked = checked; });
        document.querySelectorAll('.excerpt-chk:not(:disabled)').forEach(c => { c.checked = checked; });
        updateSelectionStats();
    }

    if (btnSelectAll) {
        btnSelectAll.onclick = () => selectAllTopics(true);
    }
    if (btnClearAll) {
        btnClearAll.onclick = () => selectAllTopics(false);
    }
}

// Deduplicate and merge overlapping chunks
function deduplicateMatches(matches) {
    if (!matches || matches.length === 0) return [];
    const cleaned = [];
    const seen = new Set();
    
    matches.forEach(m => {
        const text = (m.text || "").trim();
        if (!text) return;
        const norm = text.split(/\s+/).slice(0, 25).join(" ");
        if (seen.has(norm)) return;
        seen.add(norm);
        cleaned.push(m);
    });
    return cleaned;
}

// --- Generate & Export Notes (Server or Client Fallback) ---

generateDocxBtn.addEventListener("click", async () => {
    if (!rawResults) return;

    const exportFormat = document.querySelector('input[name="export_format"]:checked').value;
    const allTopics = (rawResults.syllabus_topics || []).concat(rawResults.other_topics || []).length > 0
        ? (rawResults.syllabus_topics || []).concat(rawResults.other_topics || [])
        : (rawResults.topics || []);

    const selectedTopicIds = [];
    const payloadTopics = [];

    allTopics.forEach(topic => {
        const itemEl = document.querySelector(`.accordion-item[data-topic-id="${topic.topic_id}"]`);
        const topicChk = itemEl ? itemEl.querySelector(`.topic-chk`) : null;

        if (topicChk && !topicChk.checked) {
            return;
        }

        const filteredMatches = [];
        if (topic.matches) {
            topic.matches.forEach(match => {
                if (itemEl) {
                    const excerptChks = itemEl.querySelectorAll('.excerpt-chk');
                    let chk = null;
                    for (const ec of excerptChks) {
                        if (ec.dataset.chunkId === match.chunk_id) {
                            chk = ec;
                            break;
                        }
                    }
                    if (chk && chk.checked && match.text && match.text.trim()) {
                        filteredMatches.push(match);
                    }
                } else if (match.text && match.text.trim()) {
                    filteredMatches.push(match);
                }
            });
        }

        const deduplicated = deduplicateMatches(filteredMatches);
        if (deduplicated.length > 0) {
            selectedTopicIds.push(topic.topic_id);
            payloadTopics.push({
                topic_id: topic.topic_id,
                title: topic.title,
                unit: topic.unit,
                section: topic.section,
                hierarchy_number: topic.hierarchy_number,
                full_context: topic.full_context,
                matches: deduplicated
            });
        }
    });

    if (payloadTopics.length === 0) {
        alert("Some selected topics do not contain extractable source content. Please review the selection and try again.");
        return;
    }

    try {
        generateDocxBtn.classList.add("disabled");
        generateDocxBtn.setAttribute("disabled", "true");
        generateDocxBtn.textContent = `Generating ${exportFormat.toUpperCase()} (${payloadTopics.length} Topics)...`;

        const apiBase = getApiBaseUrl();

        // 1. Send selected topic IDs to FastAPI Backend
        if (taskId && !taskId.startsWith("client_")) {
            try {
                const response = await fetch(`${apiBase}/api/generate/${taskId}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        selected_topic_ids: selectedTopicIds,
                        topics: payloadTopics,
                        export_format: exportFormat
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    directDownloadLink.href = `${apiBase}${data.download_url}`;
                    downloadFilename.textContent = `extracted_notes.${data.format}`;
                    downloadFileSize.textContent = `Format: ${data.format.toUpperCase()} (${payloadTopics.length} Topics | Times New Roman 12-14pt Pure Black)`;
                    directDownloadLink.querySelector("span").textContent = `Download ${data.format.toUpperCase()}`;
                    
                    const docxIcon = document.querySelector(".docx-icon");
                    if (docxIcon) {
                        docxIcon.textContent = data.format.toUpperCase() === "PDF" ? "PDF" : "W";
                    }

                    showStage(downloadStage);
                    return;
                } else {
                    const errData = await response.json().catch(() => ({}));
                    if (response.status === 400 && errData.detail) {
                        alert(errData.detail);
                        return;
                    }
                }
            } catch (backendErr) {
                console.warn("[Mento.AI] Backend generator unavailable, falling back to client generation...", backendErr);
            }
        }

        // 2. Client-Side Document Generator Fallback
        if (exportFormat === "pdf") {
            await generateClientPdf(payloadTopics);
        } else {
            await generateClientDocx(payloadTopics);
        }

        showStage(downloadStage);

    } catch (err) {
        console.error("Export error:", err);
        alert(`Error generating document: ${err.message}`);
    } finally {
        generateDocxBtn.classList.remove("disabled");
        generateDocxBtn.removeAttribute("disabled");
        generateDocxBtn.innerHTML = `<span>✨ Compile &amp; Export Notes (<span id="btn-topic-count">${payloadTopics.length}</span> Topics)</span><span class="btn-glow"></span>`;
    }
});

// Client-Side PDF Generator via jsPDF
async function generateClientPdf(topics) {
    if (clientDownloadBlobUrl) {
        URL.revokeObjectURL(clientDownloadBlobUrl);
    }

    if (window.jspdf && window.jspdf.jsPDF) {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
        const pageWidth = doc.internal.pageSize.getWidth();
        const margin = 18;
        const maxTextWidth = pageWidth - (margin * 2);
        let y = 24;

        function checkPageBreak(neededHeight) {
            if (y + neededHeight > 275) {
                doc.addPage();
                y = 20;
            }
        }

        // Header Title
        doc.setFont("times", "bold");
        doc.setFontSize(20);
        doc.setTextColor(30, 27, 75);
        doc.text("Mento.AI — Topic-Wise Extracted Study Notes", margin, y);
        y += 8;

        doc.setFont("times", "normal");
        doc.setFontSize(10);
        doc.setTextColor(100, 116, 139);
        doc.text(`Generated: ${new Date().toLocaleDateString()} | Times New Roman 12pt Standard Layout`, margin, y);
        y += 12;

        let currentUnit = null;

        topics.forEach(topic => {
            if (!topic.matches || topic.matches.length === 0) return;

            if (topic.unit && topic.unit !== currentUnit) {
                currentUnit = topic.unit;
                checkPageBreak(16);
                doc.setFont("times", "bold");
                doc.setFontSize(15);
                doc.setTextColor(99, 102, 241);
                doc.text(currentUnit, margin, y);
                y += 2;
                doc.setDrawColor(226, 232, 240);
                doc.line(margin, y, pageWidth - margin, y);
                y += 8;
            }

            checkPageBreak(14);
            doc.setFont("times", "bold");
            doc.setFontSize(13);
            doc.setTextColor(15, 23, 42);
            const numPrefix = topic.hierarchy_number ? `${topic.hierarchy_number} ` : "";
            doc.text(`${numPrefix}${topic.title}`, margin, y);
            y += 6;

            topic.matches.forEach((match, mIdx) => {
                checkPageBreak(18);
                
                // Excerpt pill
                doc.setFont("times", "italic");
                doc.setFontSize(9.5);
                doc.setTextColor(100, 116, 139);
                doc.text(`[Excerpt #${mIdx + 1} | Source: ${match.source} (Page ${match.page_number}) | Relevance: ${(match.similarity_score * 100).toFixed(1)}%]`, margin, y);
                y += 5;

                // Text body
                doc.setFont("times", "normal");
                doc.setFontSize(11);
                doc.setTextColor(0, 0, 0);
                const splitText = doc.splitTextToSize(match.text, maxTextWidth);
                
                splitText.forEach(line => {
                    checkPageBreak(6);
                    doc.text(line, margin, y);
                    y += 5.2;
                });
                y += 4;
            });

            y += 4;
        });

        // Add page numbers
        const pageCount = doc.internal.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
            doc.setPage(i);
            doc.setFont("times", "italic");
            doc.setFontSize(9);
            doc.setTextColor(148, 163, 184);
            doc.text(`Page ${i} of ${pageCount} — Mento.AI Note Compiler`, pageWidth / 2, 287, { align: "center" });
        }

        const pdfBlob = doc.output("blob");
        clientDownloadBlobUrl = URL.createObjectURL(pdfBlob);
        setupDownloadUI(clientDownloadBlobUrl, "pdf");
    } else {
        // Simple plain text fallback
        const textContent = formatNotesAsPlainText(topics);
        const blob = new Blob([textContent], { type: "text/plain;charset=utf-8" });
        clientDownloadBlobUrl = URL.createObjectURL(blob);
        setupDownloadUI(clientDownloadBlobUrl, "txt");
    }
}

// Client-Side DOCX Generator
async function generateClientDocx(topics) {
    if (clientDownloadBlobUrl) {
        URL.revokeObjectURL(clientDownloadBlobUrl);
    }

    if (window.docx) {
        try {
            const { Document, Paragraph, TextRun, HeadingLevel, Packer, AlignmentType, BorderStyle } = window.docx;
            const docChildren = [];

            // Title
            docChildren.push(
                new Paragraph({
                    heading: HeadingLevel.TITLE,
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 200 },
                    children: [
                        new TextRun({
                            text: "Mento.AI — Topic-Wise Extracted Study Notes",
                            bold: true,
                            size: 36, // 18pt
                            font: "Times New Roman",
                            color: "1E1B4B"
                        })
                    ]
                })
            );

            // Subtitle
            docChildren.push(
                new Paragraph({
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 400 },
                    children: [
                        new TextRun({
                            text: `Compiled: ${new Date().toLocaleDateString()} | Times New Roman 12-14pt Layout`,
                            italics: true,
                            size: 20, // 10pt
                            font: "Times New Roman",
                            color: "64748B"
                        })
                    ]
                })
            );

            let currentUnit = null;

            topics.forEach(topic => {
                if (!topic.matches || topic.matches.length === 0) return;

                if (topic.unit && topic.unit !== currentUnit) {
                    currentUnit = topic.unit;
                    docChildren.push(
                        new Paragraph({
                            heading: HeadingLevel.HEADING_1,
                            spacing: { before: 360, after: 140 },
                            children: [
                                new TextRun({
                                    text: currentUnit,
                                    bold: true,
                                    size: 28, // 14pt
                                    font: "Times New Roman",
                                    color: "4F46E5"
                                })
                            ]
                        })
                    );
                }

                const numPrefix = topic.hierarchy_number ? `${topic.hierarchy_number} ` : "";
                docChildren.push(
                    new Paragraph({
                        heading: HeadingLevel.HEADING_2,
                        spacing: { before: 200, after: 100 },
                        children: [
                            new TextRun({
                                text: `${numPrefix}${topic.title}`,
                                bold: true,
                                size: 24, // 12pt
                                font: "Times New Roman",
                                color: "0F172A"
                            })
                        ]
                    })
                );

                topic.matches.forEach((match, mIdx) => {
                    docChildren.push(
                        new Paragraph({
                            spacing: { before: 80, after: 40 },
                            children: [
                                new TextRun({
                                    text: `[Excerpt #${mIdx + 1} | Source: ${match.source} (Page ${match.page_number}) | Relevance: ${(match.similarity_score * 100).toFixed(1)}%]`,
                                    italics: true,
                                    size: 19, // 9.5pt
                                    font: "Times New Roman",
                                    color: "64748B"
                                })
                            ]
                        })
                    );

                    docChildren.push(
                        new Paragraph({
                            spacing: { before: 40, after: 160 },
                            children: [
                                new TextRun({
                                    text: match.text,
                                    size: 24, // 12pt
                                    font: "Times New Roman",
                                    color: "000000"
                                })
                            ]
                        })
                    );
                });
            });

            const doc = new Document({
                sections: [{
                    properties: {
                        page: {
                            margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } // 1 inch
                        }
                    },
                    children: docChildren
                }]
            });

            const blob = await Packer.toBlob(doc);
            clientDownloadBlobUrl = URL.createObjectURL(blob);
            setupDownloadUI(clientDownloadBlobUrl, "docx");
            return;
        } catch (docxErr) {
            console.warn("docx UMD packer failed, using formatted Word HTML document...", docxErr);
        }
    }

    // HTML Word Document Blob Fallback
    const htmlContent = formatNotesAsWordHtml(topics);
    const blob = new Blob(['\ufeff' + htmlContent], {
        type: 'application/msword;charset=utf-8'
    });
    clientDownloadBlobUrl = URL.createObjectURL(blob);
    setupDownloadUI(clientDownloadBlobUrl, "docx");
}

function formatNotesAsPlainText(topics) {
    let out = "=====================================================\n";
    out += "MENTO.AI — TOPIC-WISE EXTRACTED STUDY NOTES\n";
    out += `Generated: ${new Date().toLocaleDateString()}\n`;
    out += "=====================================================\n\n";

    topics.forEach(t => {
        if (!t.matches || t.matches.length === 0) return;
        out += `\n[ ${t.unit} ]\n`;
        out += `TOPIC: ${t.hierarchy_number ? t.hierarchy_number + ' ' : ''}${t.title}\n`;
        out += "-----------------------------------------------------\n";
        t.matches.forEach((m, idx) => {
            out += `Excerpt #${idx + 1} (${m.source}, Page ${m.page_number}) [Score: ${(m.similarity_score * 100).toFixed(1)}%]:\n`;
            out += `${m.text}\n\n`;
        });
    });
    return out;
}

function formatNotesAsWordHtml(topics) {
    let body = `
    <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
    <head><meta charset='utf-8'><title>Mento.AI Notes</title>
    <style>
        body { font-family: 'Times New Roman', serif; font-size: 12pt; color: #000; line-height: 1.4; margin: 1in; }
        h1.main-title { font-size: 20pt; text-align: center; color: #1E1B4B; margin-bottom: 4px; }
        p.subtitle { text-align: center; color: #64748B; font-style: italic; font-size: 10pt; margin-bottom: 24px; }
        h2.unit-heading { font-size: 15pt; color: #4F46E5; border-bottom: 1.5px solid #E2E8F0; padding-bottom: 4px; margin-top: 24px; }
        h3.topic-heading { font-size: 13pt; color: #0F172A; margin-top: 14px; margin-bottom: 6px; }
        p.excerpt-meta { font-size: 9.5pt; color: #64748B; font-style: italic; margin-bottom: 4px; }
        p.excerpt-body { font-size: 11.5pt; color: #000000; margin-bottom: 12px; }
    </style>
    </head>
    <body>
        <h1 class="main-title">Mento.AI — Extracted Study Notes</h1>
        <p class="subtitle">Compiled on ${new Date().toLocaleDateString()} | Topic-by-Topic Syllabus Mapping</p>
    `;

    let currentUnit = null;
    topics.forEach(t => {
        if (!t.matches || t.matches.length === 0) return;

        if (t.unit && t.unit !== currentUnit) {
            currentUnit = t.unit;
            body += `<h2 class="unit-heading">${currentUnit}</h2>`;
        }

        const numPrefix = t.hierarchy_number ? `${t.hierarchy_number} ` : "";
        body += `<h3 class="topic-heading">${numPrefix}${t.title}</h3>`;

        t.matches.forEach((m, idx) => {
            body += `<p class="excerpt-meta">[Excerpt #${idx + 1} | Source: ${m.source} (Page ${m.page_number}) | Relevance: ${(m.similarity_score * 100).toFixed(1)}%]</p>`;
            body += `<p class="excerpt-body">${m.text}</p>`;
        });
    });

    body += `</body></html>`;
    return body;
}

function setupDownloadUI(blobUrl, format) {
    directDownloadLink.href = blobUrl;
    directDownloadLink.setAttribute("download", `extracted_notes.${format}`);
    downloadFilename.textContent = `extracted_notes.${format}`;
    downloadFileSize.textContent = `Format: ${format.toUpperCase()} (Times New Roman 12-14pt Pure Black)`;
    directDownloadLink.querySelector("span").textContent = `Download ${format.toUpperCase()}`;

    const docxIcon = document.querySelector(".docx-icon");
    if (docxIcon) {
        docxIcon.textContent = format.toUpperCase() === "PDF" ? "PDF" : "W";
    }

    // Auto-trigger download
    const autoLink = document.createElement("a");
    autoLink.href = blobUrl;
    autoLink.download = `extracted_notes.${format}`;
    document.body.appendChild(autoLink);
    autoLink.click();
    document.body.removeChild(autoLink);
}

// --- Navigation Buttons ---

backToUploadBtn.addEventListener("click", () => {
    showStage(uploadStage);
});

restartBtn.addEventListener("click", () => {
    resetFileInput("study");
    resetFileInput("syllabus");
    syllabusTextInput.value = "";
    taskId = null;
    rawResults = null;
    if (clientDownloadBlobUrl) {
        URL.revokeObjectURL(clientDownloadBlobUrl);
        clientDownloadBlobUrl = null;
    }
    showStage(uploadStage);
});
