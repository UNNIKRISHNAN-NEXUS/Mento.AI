/**
 * Mento.AI — Frontend Application Controller
 * Handles multi-file uploads, text syllabus inputs, SSE progress, interactive preview selection,
 * and DOCX/PDF format export.
 */

// Application State
let studyFiles = [];
let syllabusFile = null;
let syllabusMode = "file"; // "file" or "text"
let taskId = null;
let rawResults = null;

// API Configuration — Defaults to same-origin for unified Vercel deployment
function getApiBaseUrl() {
    const savedUrl = localStorage.getItem("MENTO_BACKEND_URL");
    if (savedUrl && savedUrl.trim()) {
        return savedUrl.trim().replace(/\/+$/, '');
    }
    // Unified same-origin backend on Vercel and local
    return "";
}

function setCustomBackendUrl(newUrl) {
    if (newUrl && newUrl.trim()) {
        const cleanUrl = newUrl.trim().replace(/\/+$/, '');
        localStorage.setItem("MENTO_BACKEND_URL", cleanUrl);
        return cleanUrl;
    }
    return getApiBaseUrl();
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

if (toggleMathMode && chkMathMode) {
    toggleMathMode.addEventListener("click", (e) => {
        e.preventDefault();
        chkMathMode.checked = !chkMathMode.checked;
        toggleMathMode.classList.toggle("active", chkMathMode.checked);
    });
}

if (toggleHandwritingMode && chkHandwritingMode) {
    toggleHandwritingMode.addEventListener("click", (e) => {
        e.preventDefault();
        chkHandwritingMode.checked = !chkHandwritingMode.checked;
        toggleHandwritingMode.classList.toggle("active", chkHandwritingMode.checked);
    });
}

// --- Format Selector Toggle ---

choiceDocx.addEventListener("click", () => {
    choiceDocx.classList.add("active");
    choicePdf.classList.remove("active");
    choiceDocx.querySelector("input").checked = true;
});

choicePdf.addEventListener("click", () => {
    choicePdf.classList.add("active");
    choiceDocx.classList.remove("active");
    choicePdf.querySelector("input").checked = true;
});

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

// --- Upload & SSE Pipeline Processing ---

startProcessBtn.addEventListener("click", async () => {
    if (studyFiles.length === 0) return;
    if (syllabusMode === "file" && !syllabusFile) return;
    if (syllabusMode === "text" && !syllabusTextInput.value.trim()) return;

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

    try {
        showStage(processingStage);
        progressBarFill.style.width = "0%";
        progressPct.textContent = "0%";
        progressStatusTitle.textContent = "Uploading study files & syllabus...";

        const response = await fetch(`${apiBase}/api/upload`, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            if (response.status === 404 || response.status === 502 || response.status === 503) {
                const promptUrl = prompt(
                    `Backend connection error (${response.status}) at:\n${apiBase}\n\nIf your Render backend URL is different, please enter it below (e.g., https://your-render-app.onrender.com):`,
                    apiBase
                );
                if (promptUrl && promptUrl.trim()) {
                    setCustomBackendUrl(promptUrl);
                    alert("Render Backend URL saved! Click 'Start Processing' again.");
                }
                showStage(uploadStage);
                return;
            }
            let errorMsg = "Upload failed";
            try {
                const err = await response.json();
                errorMsg = err.detail || errorMsg;
            } catch (e) {
                errorMsg = response.statusText || `Server Error (${response.status})`;
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        taskId = data.task_id;
        
        if (data.results) {
            // Instant result from synchronous Vercel Serverless execution
            progressBarFill.style.width = "100%";
            progressPct.textContent = "100%";
            progressStatusTitle.textContent = "Extraction & matching complete!";
            rawResults = data.results;
            renderPreview(data.results);
            showStage(previewStage);
        } else {
            startProgressMonitoring(taskId);
        }
    } catch (err) {
        if (err.message.includes("Failed to fetch") || err.name === "TypeError") {
            const promptUrl = prompt(
                `Backend connection error at:\n${apiBase}\n\nIf your backend URL is different (e.g. https://mento-ai-backend-sc4k.onrender.com), please enter it below:`,
                apiBase || "https://mento-ai-backend-sc4k.onrender.com"
            );
            if (promptUrl && promptUrl.trim()) {
                setCustomBackendUrl(promptUrl);
                alert("Backend URL saved! Click 'Start Processing' again.");
            }
        } else {
            alert(`Error starting task: ${err.message}`);
        }
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

    // 1. Primary SSE Streaming
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

    // 2. Fail-Safe REST Polling Fallback
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

// --- Fetch & Render Preview ---

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
    let totalMatches = 0;
    let currentUnit = null;

    results.topics.forEach(topic => {
        const matchesCount = topic.matches.length;
        totalMatches += matchesCount;

        if (topic.unit && topic.unit !== currentUnit) {
            currentUnit = topic.unit;
            const unitHeader = document.createElement("div");
            unitHeader.className = "unit-header-accordion";
            unitHeader.textContent = currentUnit;
            resultsAccordion.appendChild(unitHeader);
        }

        const accItem = document.createElement("div");
        accItem.className = "accordion-item";
        accItem.dataset.topicId = topic.topic_id;

        const accHeader = document.createElement("div");
        accHeader.className = "accordion-header";
        
        const titleBlock = document.createElement("div");
        titleBlock.className = "accordion-title-block";
        
        if (topic.hierarchy_number) {
            const numSpan = document.createElement("span");
            numSpan.className = "accordion-num";
            numSpan.textContent = topic.hierarchy_number;
            titleBlock.appendChild(numSpan);
        }
        
        const titleSpan = document.createElement("span");
        titleSpan.className = "accordion-title";
        titleSpan.textContent = topic.title;
        titleSpan.title = topic.full_context;
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
            noMatchMsg.textContent = "No matching excerpts extracted for this topic.";
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
                chk.checked = true;
                chk.id = `chk-${topic.topic_id}-${match.chunk_id}`;
                
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
            });
        }

        accItem.appendChild(accHeader);
        accItem.appendChild(accBody);

        accHeader.addEventListener("click", () => {
            accItem.classList.toggle("open");
        });

        resultsAccordion.appendChild(accItem);
    });

    previewTotalMatches.textContent = totalMatches;
}

// --- Generate & Export (DOCX or PDF) ---

generateDocxBtn.addEventListener("click", async () => {
    if (!rawResults || !taskId) return;

    const exportFormat = document.querySelector('input[name="export_format"]:checked').value;
    const payloadTopics = [];

    rawResults.topics.forEach(topic => {
        const itemEl = document.querySelector(`.accordion-item[data-topic-id="${topic.topic_id}"]`);
        if (!itemEl) return;

        const filteredMatches = [];
        topic.matches.forEach(match => {
            const chk = itemEl.querySelector(`#chk-${topic.topic_id}-${match.chunk_id}`);
            if (chk && chk.checked) {
                filteredMatches.push(match);
            }
        });

        payloadTopics.push({
            topic_id: topic.topic_id,
            title: topic.title,
            unit: topic.unit,
            section: topic.section,
            hierarchy_number: topic.hierarchy_number,
            full_context: topic.full_context,
            matches: filteredMatches
        });
    });

    try {
        generateDocxBtn.classList.add("disabled");
        generateDocxBtn.setAttribute("disabled", "true");
        generateDocxBtn.textContent = `Generating ${exportFormat.toUpperCase()}...`;

        const apiBase = getApiBaseUrl();
        const response = await fetch(`${apiBase}/api/generate/${taskId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                topics: payloadTopics,
                export_format: exportFormat
            })
        });

        if (!response.ok) {
            throw new Error(`Failed to generate ${exportFormat.toUpperCase()}`);
        }

        const data = await response.json();
        
        directDownloadLink.href = `${apiBase}${data.download_url}`;
        downloadFilename.textContent = `extracted_notes.${data.format}`;
        downloadFileSize.textContent = `Format: ${data.format.toUpperCase()} (Times New Roman 12-14pt Pure Black)`;
        directDownloadLink.querySelector("span").textContent = `Download ${data.format.toUpperCase()}`;
        
        const docxIcon = document.querySelector(".docx-icon");
        if (docxIcon) {
            docxIcon.textContent = data.format.toUpperCase() === "PDF" ? "PDF" : "W";
        }

        showStage(downloadStage);
    } catch (err) {
        alert(`Error generating document: ${err.message}`);
    } finally {
        generateDocxBtn.classList.remove("disabled");
        generateDocxBtn.removeAttribute("disabled");
        generateDocxBtn.innerHTML = `<span>Compile & Export Notes</span><span class="btn-glow"></span>`;
    }
});

backToUploadBtn.addEventListener("click", () => {
    showStage(uploadStage);
});

restartBtn.addEventListener("click", () => {
    resetFileInput("study");
    resetFileInput("syllabus");
    syllabusTextInput.value = "";
    taskId = null;
    rawResults = null;
    showStage(uploadStage);
});
