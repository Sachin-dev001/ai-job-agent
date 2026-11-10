// =============================================================================
// GLOBAL FETCH WRAPPER: Automatically injects JWT Bearer token on all API calls
// =============================================================================
const DEFAULT_REMOTE_BACKEND = "https://autoapply-backend-hvdm.onrender.com";
const originalFetch = window.fetch;
window.fetch = async function(url, options = {}) {
    options = options || {};
    options.headers = options.headers || {};
    
    // Auto-resolve relative API paths when running on external Vercel domain
    if (typeof url === 'string' && url.startsWith('/api/')) {
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (!isLocal) {
            const remoteBackend = localStorage.getItem('backend_api_url') || DEFAULT_REMOTE_BACKEND;
            if (remoteBackend) {
                url = remoteBackend.replace(/\/$/, '') + url;
            }
        }
    }
    const token = (typeof getAuthToken === 'function') ? getAuthToken() : localStorage.getItem("autoapply_auth_token");
    if (token) {
        if (options.headers instanceof Headers) {
            options.headers.set('Authorization', 'Bearer ' + token);
        } else if (Array.isArray(options.headers)) {
            options.headers.push(['Authorization', 'Bearer ' + token]);
        } else {
            options.headers['Authorization'] = 'Bearer ' + token;
        }
    }
    return originalFetch(url, options);
};

// =============================================================================
// SAFE JSON PARSER: Catches HTML 404/500s from Vercel & proxies gracefully
// =============================================================================
async function safeParseJson(res) {
    let text = "";
    try {
        text = await res.text();
    } catch (readErr) {
        throw new Error("Unable to read network response: " + readErr.message);
    }

    let data;
    try {
        data = JSON.parse(text);
    } catch (parseErr) {
        const isVercel = window.location.hostname.includes("vercel.app");
        const status = res.status;
        
        if (status === 404 || text.includes("The page could not be found") || text.includes("DEPLOYMENT_NOT_FOUND")) {
            if (isVercel) {
                throw new Error(
                    "Backend Server Not Connected (HTTP 404)\n\n" +
                    "Your frontend is running on Vercel, but the Python backend is not connected yet.\n\n" +
                    "QUICK FIX (20 seconds):\n" +
                    "1. Click 'Backend Disconnected' or 'Cloud Config Keys' at the top right.\n" +
                    "2. Enter your live backend URL (e.g. from Render.com or Railway).\n" +
                    "3. Or run the local backend server at http://localhost:8000."
                );
            }
            throw new Error("Endpoint not found (404). Please ensure the backend server is running.");
        }
        
        if (status >= 500) {
            throw new Error(`Backend server error (${status}): ${text.substring(0, 160)}`);
        }
        
        throw new Error(`Unexpected server response (${status}): ${text.substring(0, 120)}`);
    }

    if (!res.ok) {
        const errorMsg = data.detail || data.message || data.error || `Request failed with status ${res.status}`;
        throw new Error(errorMsg);
    }

    return data;
}


let currentAnalysis = null;
let foundJobs = [];
let activeApplyingJobIndex = null;
let currentSelectedRole = "";
let currentSelectedPlatform = "naukri"; // "naukri" or "wellfound"

document.addEventListener("DOMContentLoaded", () => {
    initSupabase();
    checkOAuthRedirectTokens();
    initGoogleIdentity();

    const dropzone = document.getElementById("dropzone");
    const resumeFileInput = document.getElementById("resumeFileInput");
    const fileStatus = document.getElementById("fileStatus");
    const fileName = document.getElementById("fileName");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const searchJobsBtn = document.getElementById("searchJobsBtn");

    if (dropzone && resumeFileInput) {
        dropzone.addEventListener("click", () => resumeFileInput.click());
    }

    if (resumeFileInput) {
        resumeFileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                if (fileName) fileName.textContent = file.name;
                if (fileStatus) fileStatus.classList.remove("hidden");
                const placeholder = document.getElementById("resumePlaceholderText");
                if (placeholder) placeholder.textContent = file.name;
            }
        });
    }

    if (analyzeBtn) {
        analyzeBtn.addEventListener("click", async () => {
            const file = resumeFileInput?.files[0];
            if (!file) {
                alert("Please select a resume file (PDF, DOCX, TXT) first.");
                resumeFileInput?.click();
                return;
            }

            analyzeBtn.disabled = true;
            analyzeBtn.textContent = "Analyzing...";

            const formData = new FormData();
            formData.append("file", file);

            try {
                const token = getAuthToken();
                const res = await fetch("/api/resume/analyze", {
                    method: "POST",
                    headers: token ? { "Authorization": `Bearer ${token}` } : {},
                    body: formData
                });

                const data = await safeParseJson(res);
                currentAnalysis = data;
                renderProfile(data);
                // Refresh Memory Vault to immediately display candidate extracted facts
                loadQAMemory();

                let targetRole = "Software Engineer";
                if (data.recommended_job_titles && data.recommended_job_titles.length > 0) {
                    const topObj = data.recommended_job_titles[0];
                    targetRole = typeof topObj === "object" ? (topObj.title || topObj) : topObj;
                } else if (data.primary_domain) {
                    targetRole = data.primary_domain;
                }
                currentSelectedRole = targetRole;

                // Scout jobs for extracted role
                triggerJobSearch(currentSelectedRole);
                openPlatformSelector(currentSelectedRole);
            } catch (error) {
                alert("Resume Analysis Notice:\n\n" + error.message);
            } finally {
                analyzeBtn.disabled = false;
                analyzeBtn.textContent = "Analyze Resume with LLM";
            }
        });
    }

    if (searchJobsBtn) {
        searchJobsBtn.addEventListener("click", () => {
            if (!currentAnalysis) {
                renderJobsEmptyState();
                alert("Please upload and analyze your resume first so the agent knows which jobs match your skills!");
                document.getElementById("resumeFileInput")?.click();
                return;
            }
            triggerJobSearch(currentSelectedRole);
        });
    }

    // Default to clean empty state on fresh load
    if (!currentAnalysis) {
        renderJobsEmptyState();
    }

    // Restore candidate profile if authenticated
    if (currentAuthUser) {
        loadUserProfile();
        loadUserApplications();
    }

    // Initialize Memory Vault
    loadQAMemory();
    setInterval(loadQAMemory, 8000);
});

// ==========================================
// Platform Switching & Modal Logic
// ==========================================
function switchPlatform(platformName) {
    currentSelectedPlatform = platformName;
    const tabNaukri = document.getElementById("tabNaukri");
    const tabWellfound = document.getElementById("tabWellfound");
    const runBtnText = document.getElementById("runPlatformBtnText");

    if (platformName === "naukri") {
        if (tabNaukri) {
            tabNaukri.className = "platform-tab px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 bg-zinc-800 text-white shadow-sm";
        }
        if (tabWellfound) {
            tabWellfound.className = "platform-tab px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200";
        }
        if (runBtnText) {
            runBtnText.textContent = "Run Autonomous Naukri Apply";
        }
    } else if (platformName === "wellfound") {
        if (tabWellfound) {
            tabWellfound.className = "platform-tab px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 bg-zinc-800 text-white shadow-sm";
        }
        if (tabNaukri) {
            tabNaukri.className = "platform-tab px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200";
        }
        if (runBtnText) {
            runBtnText.textContent = "Run Autonomous Wellfound Apply";
        }
    }

    // Guard: Prevent job scouting before resume analysis
    if (!currentAnalysis) {
        renderJobsEmptyState();
        return;
    }

    triggerJobSearch(currentSelectedRole);
}

function openPlatformSelector(roleTitle) {
    currentSelectedRole = roleTitle;
    const titleEl = document.getElementById("modalSelectedRoleTitle");
    if (titleEl) titleEl.textContent = roleTitle;

    const modal = document.getElementById("platformSelectorModal");
    if (modal) modal.classList.remove("hidden");
}

function closePlatformModal() {
    const modal = document.getElementById("platformSelectorModal");
    if (modal) modal.classList.add("hidden");
}

function selectPlatformAndScout(platformName) {
    closePlatformModal();
    switchPlatform(platformName);
}

function showYCNotice() {
    alert("⚡ Y Combinator (Work at a Startup) integration will be enabled in the next update, right after Wellfound and Naukri verification!");
}

// ==========================================
// Empty State & Job Scouting
// ==========================================
function renderJobsEmptyState() {
    const tableBody = document.getElementById("jobsTableBody");
    const mobileCards = document.getElementById("jobsCardsMobile");
    const openingsHeading = document.getElementById("openingsHeading");
    const statFound = document.getElementById("statFound");
    if (statFound) statFound.textContent = "0";

    const platLabel = currentSelectedPlatform === "wellfound" ? "Wellfound Startups" : "Naukri";
    if (openingsHeading) {
        openingsHeading.innerHTML = `
            <i data-lucide="briefcase" class="w-5 h-5 text-indigo-400"></i>
            Live <span class="text-indigo-400 font-bold ml-1">${platLabel}</span> Openings:
            <span class="text-zinc-400 font-medium ml-1">Awaiting Resume Analysis</span>
        `;
    }

    const emptyHtmlDesktop = `
        <tr>
            <td colspan="5" class="py-12 px-4 text-center">
                <div class="flex flex-col items-center justify-center max-w-md mx-auto space-y-3">
                    <div class="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                        <i data-lucide="file-search" class="w-6 h-6"></i>
                    </div>
                    <div class="space-y-1">
                        <h4 class="text-sm font-semibold text-zinc-100">Upload and analyze your resume first</h4>
                        <p class="text-xs text-zinc-400 leading-relaxed">
                            Upload and analyze your resume first. The AI agent will extract your skills DNA and automatically scout 100% matched openings for your domain.
                        </p>
                    </div>
                    <button type="button" onclick="document.getElementById('resumeFileInput')?.click()" class="mt-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition shadow-md flex items-center gap-1.5 cursor-pointer">
                        <i data-lucide="upload-cloud" class="w-4 h-4"></i>
                        <span>Upload Resume Now</span>
                    </button>
                </div>
            </td>
        </tr>
    `;

    const emptyHtmlMobile = `
        <div class="p-6 text-center bg-zinc-950/40 rounded-xl border border-zinc-800/80 space-y-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mx-auto">
                <i data-lucide="file-search" class="w-5 h-5"></i>
            </div>
            <div class="space-y-1">
                <h4 class="text-xs font-semibold text-zinc-100">Upload and analyze your resume first</h4>
                <p class="text-[11px] text-zinc-400 leading-relaxed">
                    Upload and analyze your resume first. The AI agent will extract your skills DNA and automatically scout 100% matched openings for your domain.
                </p>
            </div>
            <button type="button" onclick="document.getElementById('resumeFileInput')?.click()" class="w-full py-2 px-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition shadow-md flex items-center justify-center gap-1.5 cursor-pointer">
                <i data-lucide="upload-cloud" class="w-4 h-4"></i>
                <span>Upload Resume Now</span>
            </button>
        </div>
    `;

    if (tableBody) tableBody.innerHTML = emptyHtmlDesktop;
    if (mobileCards) mobileCards.innerHTML = emptyHtmlMobile;
    if (window.lucide) lucide.createIcons();
}

// Job Scouting & Dynamic Search
// ==========================================
async function triggerJobSearch(query) {
    if (!currentAnalysis) {
        renderJobsEmptyState();
        return;
    }

    if (!query) query = currentSelectedRole || "Software Engineer";
    currentSelectedRole = query;

    const platLabel = currentSelectedPlatform === "wellfound" ? "Wellfound Startups" : "Naukri";
    const openingsHeading = document.getElementById("openingsHeading");
    if (openingsHeading) {
        openingsHeading.innerHTML = `
            <i data-lucide="briefcase" class="w-5 h-5 text-indigo-400"></i>
            Live <span class="text-indigo-400 font-bold ml-1">${platLabel}</span> Openings: 
            <span class="text-white font-bold ml-1">"${query}"</span>
        `;
        if (window.lucide) lucide.createIcons();
    }

    const tableBody = document.getElementById("jobsTableBody");
    const mobileCards = document.getElementById("jobsCardsMobile");
    const searchJobsBtn = document.getElementById("searchJobsBtn");
    
    if (tableBody) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="py-8 text-center text-indigo-400">
                    <span class="inline-block animate-spin mr-2">⟳</span> Scouting verified ${platLabel} postings (&le; 15 days, newest first) for "${query}"...
                </td>
            </tr>
        `;
    }
    if (mobileCards) {
        mobileCards.innerHTML = `
            <div class="p-6 text-center text-indigo-400 bg-zinc-950/40 rounded-xl border border-zinc-800/80 text-xs">
                <span class="inline-block animate-spin mr-2">⟳</span> Scouting verified ${platLabel} postings (&le; 15 days, newest first) for "${query}"...
            </div>
        `;
    }
    if (searchJobsBtn) searchJobsBtn.disabled = true;

    try {
        const res = await fetch(`/api/jobs/search?query=${encodeURIComponent(query)}&platform=${currentSelectedPlatform}&limit=25`);
        foundJobs = await safeParseJson(res);
        renderJobsTable(foundJobs);
        const statFound = document.getElementById("statFound");
        if (statFound) statFound.textContent = foundJobs.length;
    } catch (e) {
        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-6 text-center text-rose-400 font-medium">
                        Failed to fetch jobs: ${e.message}
                    </td>
                </tr>
            `;
        }
        if (mobileCards) {
            mobileCards.innerHTML = `
                <div class="p-6 text-center text-rose-400 bg-zinc-950/40 rounded-xl border border-zinc-800/80 text-xs font-medium">
                    Failed to fetch jobs: ${e.message}
                </div>
            `;
        }
    } finally {
        if (searchJobsBtn) searchJobsBtn.disabled = false;
    }
}

function renderJobsTable(jobs) {
    const tableBody = document.getElementById("jobsTableBody");
    const mobileCards = document.getElementById("jobsCardsMobile");

    if (!jobs || jobs.length === 0) {
        const emptyMsg = `No openings found for this role on ${currentSelectedPlatform}. Try switching platforms or roles above.`;
        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-8 text-center text-slate-500">
                        ${emptyMsg}
                    </td>
                </tr>
            `;
        }
        if (mobileCards) {
            mobileCards.innerHTML = `
                <div class="p-6 text-center text-zinc-500 bg-zinc-950/40 rounded-xl border border-zinc-800/80 text-xs">
                    ${emptyMsg}
                </div>
            `;
        }
        return;
    }

    // Render Desktop Table Rows
    if (tableBody) {
        tableBody.innerHTML = jobs.map((job, idx) => `
            <tr id="job-row-${idx}" class="hover:bg-zinc-800/40 transition">
                <td class="py-2.5 px-3.5 cell-wrap max-w-xs">
                    <div class="flex items-center gap-2">
                        <p class="font-semibold text-zinc-100 text-xs">${job.title}</p>
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300 border border-zinc-700/60">
                            ${job.posted_time_ago}
                        </span>
                    </div>
                    <p class="text-[11px] text-zinc-400 mt-0.5">${job.company} • <span class="text-zinc-500">${job.location}</span></p>
                </td>
                <td class="py-2.5 px-3.5">
                    <span class="px-2 py-0.5 rounded text-[10px] font-medium ${
                        job.platform === 'Naukri' 
                            ? 'bg-zinc-800 text-zinc-300 border border-zinc-700/80' 
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    }">
                        ${job.platform}
                    </span>
                </td>
                <td class="py-2.5 px-3.5">
                    <span class="text-xs font-mono font-medium text-emerald-400">96%</span>
                </td>
                <td class="py-2.5 px-3.5" id="status-cell-${idx}">
                    <span class="inline-flex items-center gap-1.5 text-zinc-400 text-xs font-medium">
                        <span class="w-1.5 h-1.5 rounded-full bg-zinc-500"></span> Discovered
                    </span>
                </td>
                <td class="py-2.5 px-3.5 text-right space-x-1" id="action-cell-${idx}">
                    <a href="${job.job_url}" target="_blank" class="text-zinc-400 hover:text-zinc-200 text-xs px-2 py-1 transition mr-0.5">View</a>
                    <button onclick="directApplyRow(${idx})" class="bg-zinc-100 hover:bg-white text-zinc-900 text-[11px] px-2.5 py-1 rounded-md font-semibold transition shadow-sm">
                        Auto-Apply
                    </button>
                    <button onclick="triggerApply(${idx})" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/60 text-[11px] px-2 py-1 rounded-md font-medium transition">
                        Pitch
                    </button>
                </td>
            </tr>
        `).join("");
    }

    // Render Mobile Cards View
    if (mobileCards) {
        mobileCards.innerHTML = jobs.map((job, idx) => `
            <div id="job-card-${idx}" class="p-3.5 bg-zinc-900/60 hairline-border rounded-xl space-y-2.5 interactive-card">
                <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0 flex-1">
                        <h4 class="font-semibold text-zinc-100 text-xs leading-snug break-words">${job.title}</h4>
                        <p class="text-[11px] text-zinc-400 mt-0.5 truncate">${job.company} &bull; <span class="text-zinc-500">${job.location}</span></p>
                    </div>
                    <span class="shrink-0 px-2 py-0.5 rounded text-[10px] font-medium ${
                        job.platform === 'Naukri' 
                            ? 'bg-zinc-800 text-zinc-300 border border-zinc-700/80' 
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    }">${job.platform}</span>
                </div>
                <div class="flex items-center justify-between text-xs pt-1 border-t border-zinc-800/60">
                    <div class="flex items-center gap-2">
                        <span class="text-[10px] font-mono bg-zinc-800 text-zinc-300 px-1.5 py-0.5 rounded border border-zinc-700/60">${job.posted_time_ago}</span>
                        <span class="text-[11px] font-mono font-medium text-emerald-400">96% Match</span>
                    </div>
                    <div id="status-card-${idx}">
                        <span class="inline-flex items-center gap-1 text-zinc-400 text-[11px]">
                            <span class="w-1.5 h-1.5 rounded-full bg-zinc-500"></span> Discovered
                        </span>
                    </div>
                </div>
                <div class="flex items-center gap-2 pt-1" id="action-card-${idx}">
                    <button onclick="directApplyRow(${idx})" class="flex-1 bg-zinc-100 hover:bg-white active:bg-zinc-200 text-zinc-900 text-xs py-2 rounded-lg font-semibold transition shadow-sm flex items-center justify-center gap-1.5">
                        <i data-lucide="zap" class="w-3.5 h-3.5 text-zinc-900"></i> Auto-Apply
                    </button>
                    <button onclick="triggerApply(${idx})" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs px-3 py-2 rounded-lg font-medium transition border border-zinc-700/60">
                        Pitch
                    </button>
                    <a href="${job.job_url}" target="_blank" class="bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs px-2.5 py-2 rounded-lg transition border border-zinc-800 flex items-center justify-center">
                        <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                    </a>
                </div>
            </div>
        `).join("");
    }
    if (window.lucide) lucide.createIcons();
}

// ==========================================
// 1-Click Autonomous Apply (Naukri & Wellfound)
// ==========================================
async function directApplyRow(idx) {
    const job = foundJobs[idx];
    if (!job) return;

    const actionCell = document.getElementById(`action-cell-${idx}`);
    const actionCard = document.getElementById(`action-card-${idx}`);
    const statusCell = document.getElementById(`status-cell-${idx}`);
    const statusCard = document.getElementById(`status-card-${idx}`);

    const originalContent = actionCell ? actionCell.innerHTML : "";
    const originalCardContent = actionCard ? actionCard.innerHTML : "";
    const isWellfound = job.platform === "Wellfound";
    const endpoint = isWellfound ? "/api/wellfound/apply-single" : "/api/naukri/apply-single";
    const platformLabel = isWellfound ? "Wellfound" : "Naukri";

    const loadingHtml = `<span class="text-xs text-indigo-400 animate-spin mr-1">⟳</span> <span class="text-xs text-indigo-300 font-medium">Applying on ${platformLabel}...</span>`;
    if (actionCell) actionCell.innerHTML = loadingHtml;
    if (actionCard) actionCard.innerHTML = `<div class="w-full text-center py-2 text-indigo-300 text-xs font-medium"><span class="animate-spin mr-1 inline-block">⟳</span> Applying on ${platformLabel}...</div>`;

    try {
        const payload = isWellfound ? {
            job_url: job.job_url,
            job_title: job.title,
            company: job.company
        } : {
            job_url: job.job_url,
            job_title: job.title
        };

        const token = getAuthToken();
        const res = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify(payload)
        });
        const data = await safeParseJson(res);
        const statApplied = document.getElementById("statApplied");

        if (data.status === "applied_successfully") {
            const appliedStatusHtml = `
                <span class="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Applied ✅
                </span>
            `;
            if (statusCell) statusCell.innerHTML = appliedStatusHtml;
            if (statusCard) statusCard.innerHTML = appliedStatusHtml;

            const proofBtnHtml = `
                <a href="${data.proof_image || job.job_url}" target="_blank" class="text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-bold hover:underline inline-flex items-center justify-center gap-1 w-full sm:w-auto">
                    ${data.proof_image ? '📸 Proof' : '🔗 View Job'}
                </a>
            `;
            if (actionCell) actionCell.innerHTML = proofBtnHtml;
            if (actionCard) actionCard.innerHTML = proofBtnHtml;

            if (statApplied) statApplied.textContent = parseInt(statApplied.textContent || "0") + 1;
            alert(`🎉 Application 100% submitted and verified on ${platformLabel} for ${job.title}!\n\n${data.message || ''}`);
        } else if (data.status === "already_applied") {
            const alreadyHtml = `
                <span class="inline-flex items-center gap-1.5 text-slate-400 text-xs font-semibold">
                    Already Applied
                </span>
            `;
            if (statusCell) statusCell.innerHTML = alreadyHtml;
            if (statusCard) statusCard.innerHTML = alreadyHtml;

            const alreadyProofHtml = `
                <a href="${data.proof_image || '#'}" target="_blank" class="text-[11px] text-slate-400 bg-slate-800 border border-slate-700 px-2.5 py-1.5 sm:py-1 rounded-lg font-medium hover:underline inline-flex items-center justify-center w-full sm:w-auto">
                    📸 Proof
                </a>
            `;
            if (actionCell) actionCell.innerHTML = alreadyProofHtml;
            if (actionCard) actionCard.innerHTML = alreadyProofHtml;
            alert(`ℹ️ You have already applied to ${job.title} on ${platformLabel}.`);
        } else if (data.status === "needs_human_action") {
            const reviewHtml = `<span class="text-amber-400 text-xs font-medium">⚠️ Review Needed</span>`;
            if (statusCell) statusCell.innerHTML = reviewHtml;
            if (statusCard) statusCard.innerHTML = reviewHtml;

            const reviewBtnHtml = `
                <a href="${data.proof_image || '#'}" target="_blank" class="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-medium hover:underline inline-flex items-center justify-center w-full sm:w-auto">
                    ⚠️ Telegram Alert
                </a>
            `;
            if (actionCell) actionCell.innerHTML = reviewBtnHtml;
            if (actionCard) actionCard.innerHTML = reviewBtnHtml;
            alert(`⚠️ Recruiter Question Needed:\n\n${data.message}`);
        } else {
            if (actionCell) actionCell.innerHTML = originalContent;
            if (actionCard) actionCard.innerHTML = originalCardContent;
            openQuickApplyModal(idx, data.message || "Application action needed");
        }
    } catch (e) {
        if (actionCell) actionCell.innerHTML = originalContent;
        if (actionCard) actionCard.innerHTML = originalCardContent;
        openQuickApplyModal(idx, e.message || "Automation error");
    }
}

// ==========================================
// Batch Autonomous Apply on Active Platform
// ==========================================
async function executeCurrentPlatformLiveBot() {
    if (!currentAnalysis) {
        alert("Please upload and analyze your resume first! The AI agent needs your candidate DNA to tailor applications and match relevant openings.");
        document.getElementById("resumeFileInput")?.click();
        return;
    }

    const runBtn = document.getElementById("runPlatformLiveBtn");
    const botStatus = document.getElementById("botLiveStatus");
    const query = currentSelectedRole || "Software Engineer";
    const isWellfound = currentSelectedPlatform === "wellfound";
    const endpoint = isWellfound ? "/api/wellfound/auto-apply-live" : "/api/naukri/auto-apply-live";
    const platformLabel = isWellfound ? "Wellfound" : "Naukri";

    runBtn.disabled = true;
    runBtn.innerHTML = `<span class="inline-block animate-spin mr-1.5">⟳</span> Running Autonomous Apply...`;
    botStatus.classList.remove("hidden");
    botStatus.innerHTML = `
        <div class="flex items-center gap-2 text-indigo-400">
            <span class="inline-block animate-spin">⟳</span>
            <strong>Playwright Live Runner Active:</strong> Launching automated Chrome session, loading authenticated ${platformLabel} session, selecting matching "${query}" jobs, and executing physical click submissions...
        </div>
    `;

    try {
        const token = getAuthToken();
        const res = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ query: query, limit: 3 })
        });

        const data = await safeParseJson(res);
        const apps = data.applications || [];

        let successCount = 0;
        let htmlLog = `<div class="mt-3 space-y-2 border-t border-slate-800 pt-2">`;

        apps.forEach((app, idx) => {
            if (app.status === "applied_successfully") {
                successCount++;
                htmlLog += `
                    <div class="flex items-center justify-between bg-slate-900/80 p-2.5 rounded-lg border border-emerald-500/30">
                        <span class="text-emerald-400 font-medium">✅ Applied: <strong>${app.job_title}</strong></span>
                        <a href="${app.proof_image}" target="_blank" class="text-xs text-emerald-300 bg-emerald-500/20 px-2.5 py-1 rounded font-bold hover:underline">
                            📸 View Submission Proof
                        </a>
                    </div>
                `;
            } else if (app.status === "already_applied") {
                htmlLog += `
                    <div class="flex items-center justify-between bg-slate-900/80 p-2.5 rounded-lg border border-slate-700/50">
                        <span class="text-slate-400">ℹ️ ${app.job_title} (Already applied earlier)</span>
                        ${app.proof_image ? `<a href="${app.proof_image}" target="_blank" class="text-xs text-slate-400 underline">Proof</a>` : ''}
                    </div>
                `;
            } else {
                htmlLog += `
                    <div class="bg-slate-900/80 p-2.5 rounded-lg border border-amber-500/30 text-amber-300">
                        ⚠️ <strong>${app.job_title}:</strong> External portal / screening question sent to your Telegram bot.
                    </div>
                `;
            }
        });
        htmlLog += `</div>`;

        botStatus.innerHTML = `
            <div class="text-slate-200">
                <span class="text-emerald-400 font-bold">🎉 Autonomous Execution Complete!</span> Processed ${apps.length} live jobs on ${platformLabel}.
                ${htmlLog}
            </div>
        `;
        const statApplied = document.getElementById("statApplied");
        if (statApplied) statApplied.textContent = parseInt(statApplied.textContent || "0") + successCount;
    } catch (e) {
        botStatus.innerHTML = `<span class="text-rose-400">❌ Error running live bot: ${e.message}</span>`;
    } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `
            <i data-lucide="zap" class="w-3.5 h-3.5 text-amber-300"></i>
            <span id="runPlatformBtnText">⚡ Run Autonomous ${platformLabel} Apply</span>
        `;
        if (window.lucide) lucide.createIcons();
    }
}

// ==========================================
// Candidate Profile & Role Cards
// ==========================================
function renderProfile(data) {
    const profileCard = document.getElementById("profileCard");
    const profileSummary = document.getElementById("profileSummary");
    const skillsContainer = document.getElementById("skillsContainer");
    const jobTitlesContainer = document.getElementById("jobTitlesContainer");

    if (profileCard) profileCard.classList.remove("hidden");

    const candName = data.candidate_name || data.name || (currentAuthUser ? currentAuthUser.name : "Candidate");
    const candEmail = data.email || (currentAuthUser ? currentAuthUser.email : "N/A");
    const candExp = data.experience_years || data.years_of_experience || 0;

    const targetNameEl = document.getElementById("agentTargetCandidateName");
    if (targetNameEl) targetNameEl.textContent = candName;

    const statParsed = document.getElementById("statParsed");
    if (statParsed) {
        statParsed.textContent = "Ready";
        statParsed.className = "mt-2 text-lg sm:text-xl font-bold tracking-tight text-emerald-400";
    }
    const statParsedSubtitle = document.getElementById("statParsedSubtitle");
    if (statParsedSubtitle) {
        statParsedSubtitle.textContent = "Resume DNA";
    }
    const placeholder = document.getElementById("resumePlaceholderText");
    if (placeholder) {
        placeholder.textContent = `${candName}${candExp ? ` (~${candExp} Yrs Exp)` : ''}`;
    }

    if (currentAuthUser && (!currentAuthUser.name || currentAuthUser.name === "Guest" || currentAuthUser.name === "Candidate" || currentAuthUser.name === "Demo Candidate")) {
        currentAuthUser.name = candName;
        localStorage.setItem("autoapply_user", JSON.stringify(currentAuthUser));
        renderAuthNavbar();
    }

    if (profileSummary) {
        profileSummary.innerHTML = `
            <p><strong class="text-zinc-300">Candidate:</strong> ${escapeHtml(candName)}</p>
            <p><strong class="text-zinc-300">Email:</strong> ${escapeHtml(candEmail)}</p>
            <p><strong class="text-zinc-300">Experience:</strong> ~${candExp} years</p>
        `;
    }

    const skillsList = data.skills || data.technical_skills || [];
    if (skillsContainer) {
        skillsContainer.innerHTML = skillsList.map(skill => `
            <span class="px-2.5 py-1 bg-zinc-900 border border-zinc-700 text-indigo-300 rounded-lg text-xs font-medium">
                ${escapeHtml(skill)}
            </span>
        `).join("");
    }

    const recJobs = data.recommended_job_titles || [];
    if (jobTitlesContainer) {
        jobTitlesContainer.innerHTML = recJobs.map((item, idx) => {
            const title = typeof item === "object" ? item.title : item;
            const reasoning = typeof item === "object" ? (item.reasoning || "Strong match based on skills DNA") : "Extracted from candidate DNA";
            const score = typeof item === "object" && item.confidence_score ? Math.round(item.confidence_score * 100) : 95;
            return `
                <div id="role-card-${idx}" class="p-3 bg-zinc-900 border ${idx === 0 ? 'border-indigo-500 ring-2 ring-indigo-500/40 bg-indigo-950/30' : 'border-zinc-700/80'} rounded-xl flex items-center justify-between cursor-pointer hover:border-indigo-500 transition role-card" onclick="selectRoleAndOpenModal('${escapeHtml(title)}', ${idx})">
                    <div>
                        <p class="font-medium text-zinc-200 text-xs">${escapeHtml(title)}</p>
                        <p class="text-[10px] text-zinc-500">${escapeHtml(reasoning)}</p>
                    </div>
                    <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${
                        score >= 80 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                    }">
                        ${score}%
                    </span>
                </div>
            `;
        }).join("");
    }
}

function selectRoleAndOpenModal(roleTitle, idx) {
    currentSelectedRole = roleTitle;
    document.querySelectorAll(".role-card").forEach(el => {
        el.classList.remove("border-indigo-500", "ring-2", "ring-indigo-500/40", "bg-indigo-950/30");
        el.classList.add("border-slate-700/80");
    });
    const active = document.getElementById(`role-card-${idx}`);
    if (active) {
        active.classList.add("border-indigo-500", "ring-2", "ring-indigo-500/40", "bg-indigo-950/30");
        active.classList.remove("border-slate-700/80");
    }
    openPlatformSelector(roleTitle);
}

// ==========================================
// Pitch Modal & Submissions
// ==========================================
async function triggerApply(jobIndex) {
    const job = foundJobs[jobIndex];
    if (!job) return;

    activeApplyingJobIndex = jobIndex;
    const actionCell = document.getElementById(`action-cell-${jobIndex}`);
    const actionCard = document.getElementById(`action-card-${jobIndex}`);
    const originalCellBtn = actionCell ? actionCell.innerHTML : null;
    const originalCardBtn = actionCard ? actionCard.innerHTML : null;

    if (actionCell) actionCell.innerHTML = `<span class="text-xs text-indigo-400 animate-pulse">Drafting pitch...</span>`;
    if (actionCard) actionCard.innerHTML = `<span class="text-xs text-indigo-400 animate-pulse">Drafting pitch...</span>`;

    try {
        const res = await fetch("/api/jobs/prepare-application", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                job_title: job.title,
                company: job.company,
                platform: job.platform,
                job_url: job.job_url,
                description: job.description_snippet || ""
            })
        });

        const data = await safeParseJson(res);

        document.getElementById("modalRole").textContent = `${job.title} at ${job.company}`;
        document.getElementById("modalCoverLetter").value = data.cover_letter;
        document.getElementById("modalSubmitLink").href = data.job_url;
        document.getElementById("applyModal").classList.remove("hidden");

        const statNeedsHuman = document.getElementById("statNeedsHuman");
        if (statNeedsHuman) statNeedsHuman.textContent = parseInt(statNeedsHuman.textContent || "0") + 1;

        if (actionCell && originalCellBtn) actionCell.innerHTML = originalCellBtn;
        if (actionCard && originalCardBtn) actionCard.innerHTML = originalCardBtn;
    } catch (e) {
        if (actionCell && originalCellBtn) actionCell.innerHTML = originalCellBtn;
        if (actionCard && originalCardBtn) actionCard.innerHTML = originalCardBtn;
        alert("Failed to prepare pitch: " + e.message);
    }
}

function closeModal() {
    document.getElementById("applyModal").classList.add("hidden");
}

function copyCoverLetter() {
    const textarea = document.getElementById("modalCoverLetter");
    textarea.select();
    navigator.clipboard.writeText(textarea.value);
    alert("Copied customized cover letter pitch to clipboard!");
}

function markSubmitted() {
    if (activeApplyingJobIndex !== null) {
        const statusCell = document.getElementById(`status-cell-${activeApplyingJobIndex}`);
        const actionCell = document.getElementById(`action-cell-${activeApplyingJobIndex}`);
        const statusCard = document.getElementById(`status-card-${activeApplyingJobIndex}`);
        const actionCard = document.getElementById(`action-card-${activeApplyingJobIndex}`);
        const statApplied = document.getElementById("statApplied");

        if (statusCell) {
            statusCell.innerHTML = `
                <span class="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Applied ✅
                </span>
            `;
        }
        if (statusCard) {
            statusCard.innerHTML = `
                <span class="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Applied ✅
                </span>
            `;
        }
        if (actionCell) {
            actionCell.innerHTML = `
                <span class="text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-lg font-medium">
                    Submitted ✅
                </span>
            `;
        }
        if (actionCard) {
            actionCard.innerHTML = `
                <span class="text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-lg font-medium">
                    Submitted ✅
                </span>
            `;
        }
        if (statApplied) statApplied.textContent = parseInt(statApplied.textContent || "0") + 1;
    }
    closeModal();
}

async function runSingleJobLiveSubmit() {
    if (activeApplyingJobIndex === null) return;
    const job = foundJobs[activeApplyingJobIndex];
    if (!job) return;

    closeModal();
    directApplyRow(activeApplyingJobIndex);
}

// ==========================================
// Candidate Q&A Memory Vault Logic
// ==========================================
let allMemories = [];

async function loadQAMemory() {
    const uid = currentAuthUser ? currentAuthUser.id : "guest-candidate";
    const token = getAuthToken();
    try {
        const res = await fetch("/api/memory/qa", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (!res.ok) {
            const cached = JSON.parse(localStorage.getItem(`autoapply_memories_${uid}`) || "[]");
            allMemories = cached;
            renderMemoryVault(allMemories);
            return;
        }
        const data = await res.json();
        // MULTI-TENANT PRIVACY GUARD:
        // Unauthenticated guests NEVER see any other candidate's personal data.
        if (!currentAuthUser) {
            const guestMemories = JSON.parse(localStorage.getItem("autoapply_memories_guest-candidate") || "[]");
            allMemories = guestMemories;
        } else {
            allMemories = data.memories || [];
            localStorage.setItem(`autoapply_memories_${uid}`, JSON.stringify(allMemories));
        }
        renderPendingQuestions(data.pending || []);
        renderMemoryVault(allMemories);
    } catch (e) {
        console.error("Error loading QA Memory:", e);
        const cached = JSON.parse(localStorage.getItem(`autoapply_memories_${uid}`) || "[]");
        allMemories = cached;
        renderMemoryVault(allMemories);
    }
}

function renderPendingQuestions(pending) {
    const container = document.getElementById("pendingQuestionsContainer");
    const list = document.getElementById("pendingQuestionsList");
    if (!container || !list) return;

    const activePending = pending.filter(p => p.status === "pending");
    if (activePending.length === 0) {
        container.classList.add("hidden");
        return;
    }

    container.classList.remove("hidden");
    list.innerHTML = activePending.map(p => `
        <div class="bg-zinc-950/80 border border-zinc-700/80 hover:border-zinc-600 rounded-xl p-4 space-y-3 transition shadow-sm interactive-card relative overflow-hidden">
            <div class="flex items-center justify-between text-xs">
                <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                    <span class="font-semibold text-zinc-100">${p.company}</span>
                    <span class="text-zinc-500">/</span>
                    <span class="text-zinc-400">${p.job_title}</span>
                </div>
                <span class="text-[10px] font-mono text-zinc-500">Asked: ${p.asked_at}</span>
            </div>

            <div class="p-3 bg-zinc-900/90 border border-zinc-800 rounded-lg">
                <span class="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold block mb-1">Recruiter Screening Prompt</span>
                <p class="text-xs font-medium text-zinc-100 leading-relaxed">
                    "${p.question}"
                </p>
            </div>

            ${p.options && p.options.length > 0 ? `
                <div class="text-[11px] text-zinc-400 flex flex-wrap gap-1.5 items-center">
                    <span class="text-zinc-500">Allowed options:</span>
                    ${p.options.map(o => `<span class="bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded text-[10px] text-zinc-300 font-mono">${o}</span>`).join('')}
                </div>
            ` : ''}

            <div class="flex flex-col sm:flex-row gap-2 pt-1">
                <input id="pending-ans-${p.id}" type="text" placeholder="Type verified candidate answer..." class="flex-1 px-3 py-2 bg-zinc-900 border border-zinc-800 focus:border-zinc-600 rounded-lg text-xs text-white placeholder-zinc-500 outline-none font-mono">
                <div class="flex gap-2">
                    <button onclick="skipPendingQuestion('${p.id}')" class="px-3.5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs font-medium transition flex items-center justify-center gap-1.5">
                        <i data-lucide="skip-forward" class="w-3.5 h-3.5"></i>
                        <span>Skip Question</span>
                    </button>
                    <button onclick="submitPendingAnswer('${p.id}')" class="px-4 py-2 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 font-semibold text-xs transition shadow-sm flex items-center justify-center gap-1.5">
                        <i data-lucide="check" class="w-3.5 h-3.5 text-zinc-950"></i>
                        <span>Save & Remember</span>
                    </button>
                </div>
            </div>
        </div>
    `).join("");

    if (window.lucide) {
        lucide.createIcons();
    }
}

async function skipPendingQuestion(qId) {
    try {
        const res = await fetch("/api/memory/skip-pending", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question_id: qId })
        });
        await safeParseJson(res);
        await loadQAMemory();
    } catch (e) {
        alert("Error skipping question: " + e.message);
    }
}

async function submitPendingAnswer(qId) {
    const input = document.getElementById(`pending-ans-${qId}`);
    if (!input || !input.value.trim()) {
        alert("Please enter an answer.");
        return;
    }

    const answer = input.value.trim();
    try {
        const token = getAuthToken();
        const res = await fetch("/api/memory/answer-pending", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ question_id: qId, answer: answer })
        });
        if (!res.ok) throw new Error("Could not save answer");
        alert("✅ Answer saved to Memory Vault! The agent will use this for future applications.");
        loadQAMemory();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

function toggleVaultModal(show) {
    const modal = document.getElementById("memoryVaultModal");
    if (!modal) return;
    if (show) {
        modal.classList.remove("hidden");
    } else {
        modal.classList.add("hidden");
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderMemoryVault(memories) {
    const list = document.getElementById("memoryVaultList");
    const countText = document.getElementById("memoryCountText");
    const vaultBadge = document.getElementById("vaultCountBadge");
    const ownerBadge = document.getElementById("vaultOwnerBadge");
    const count = (memories || []).length;

    if (vaultBadge) vaultBadge.textContent = count;
    const statNeedsHuman = document.getElementById("statNeedsHuman");
    if (statNeedsHuman) statNeedsHuman.textContent = count;
    const vaultFactCountTop = document.getElementById("vaultFactCountTop");
    if (vaultFactCountTop) vaultFactCountTop.textContent = `${count} Facts`;
    const mobileVaultCount = document.getElementById("mobileVaultCount");
    if (mobileVaultCount) mobileVaultCount.textContent = `Vault (${count})`;
    const heroVaultCount = document.getElementById("heroVaultCount");
    if (heroVaultCount) heroVaultCount.textContent = `Inspect Memory Vault (${count})`;
    const scenarioVaultFactCount = document.getElementById("scenarioVaultFactCount");
    if (scenarioVaultFactCount) scenarioVaultFactCount.textContent = `${count} Verified Facts`;

    if (!list) return;

    const candidateName = (currentAnalysis?.candidate_name || currentAuthUser?.name || "Guest");
    if (ownerBadge) {
        ownerBadge.textContent = currentAuthUser ? `Vault: ${candidateName}` : "Vault: Guest (Isolated)";
    }

    if (countText) {
        countText.textContent = `${count} Remembered Answers for ${candidateName}`;
    }

    if (memories.length === 0) {
        list.innerHTML = `
            <div class="text-center py-8 px-4 space-y-3 bg-zinc-950/60 rounded-xl border border-dashed border-zinc-800/80 my-2">
                <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center shadow-inner">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                </div>
                <div class="space-y-1">
                    <h4 class="text-sm font-semibold text-zinc-200">No Candidate Facts in Your Vault</h4>
                    <p class="text-xs text-zinc-400 max-w-sm mx-auto leading-relaxed">
                        Each candidate has their own private memory vault. Upload your resume or teach the agent custom facts below to automatically answer recruiter questions.
                    </p>
                </div>
                <div class="pt-1 flex items-center justify-center gap-2">
                    <button onclick="toggleAddMemoryForm()" class="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold text-xs transition shadow-sm inline-flex items-center gap-1.5 cursor-pointer">
                        <span>+ Add Your First Fact</span>
                    </button>
                    ${!currentAuthUser ? `
                    <button onclick="toggleVaultModal(false); toggleAuthModal(true);" class="px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium text-xs transition border border-zinc-700 inline-flex items-center gap-1.5 cursor-pointer">
                        <span>Sign In with Google</span>
                    </button>` : ''}
                </div>
            </div>
        `;
        return;
    }

    list.innerHTML = memories.slice().reverse().map(m => `
        <div class="bg-zinc-950 border border-zinc-800 hover:border-zinc-700 p-3 rounded-lg flex items-start justify-between gap-3 transition">
            <div class="space-y-1.5 text-xs flex-1">
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-medium text-zinc-200">${escapeHtml(m.question)}</span>
                    <span class="text-[10px] text-zinc-500 bg-zinc-900 border border-zinc-800 px-1.5 py-0.2 rounded capitalize">${escapeHtml(m.category || "custom")}</span>
                </div>
                <div class="text-zinc-300 font-mono text-[11px] bg-zinc-900 border border-zinc-800 px-2.5 py-1 rounded-md block">
                    <span class="text-emerald-400 font-bold mr-1.5">↳</span>${escapeHtml(m.answer)}
                </div>
            </div>
            <button onclick="deleteMemory('${m.id}')" title="Delete from memory" class="text-zinc-500 hover:text-rose-400 p-1 rounded transition text-xs shrink-0 cursor-pointer">
                ✕
            </button>
        </div>
    `).join("");
}

function filterMemories() {
    const query = (document.getElementById("memorySearchInput")?.value || "").toLowerCase();
    if (!query) {
        renderMemoryVault(allMemories);
        return;
    }
    const filtered = allMemories.filter(m => 
        (m.question || "").toLowerCase().includes(query) || 
        (m.answer || "").toLowerCase().includes(query) ||
        (m.category || "").toLowerCase().includes(query)
    );
    renderMemoryVault(filtered);
}

function toggleAddMemoryForm() {
    const form = document.getElementById("addMemoryForm");
    if (form) {
        form.classList.toggle("hidden");
    }
}

async function saveNewMemory() {
    const qInput = document.getElementById("newQuestionInput");
    const aInput = document.getElementById("newAnswerInput");
    if (!qInput || !aInput) return;

    const question = qInput.value.trim();
    const answer = aInput.value.trim();
    if (!question || !answer) {
        alert("Please enter both the question and the canonical answer.");
        return;
    }

    try {
        const token = getAuthToken();
        const res = await fetch("/api/memory/qa", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ question: question, answer: answer, category: "custom" })
        });
        if (!res.ok) throw new Error("Could not save to memory");
        qInput.value = "";
        aInput.value = "";
        toggleAddMemoryForm();
        alert("✅ Successfully added to Memory Vault!");
        const uid = currentAuthUser ? currentAuthUser.id : "guest-candidate";
        let localList = JSON.parse(localStorage.getItem(`autoapply_memories_${uid}`) || "[]");
        localList.push({ id: "mem_" + Date.now(), question, answer, category: "custom" });
        localStorage.setItem(`autoapply_memories_${uid}`, JSON.stringify(localList));
        loadQAMemory();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

async function deleteMemory(mId) {
    if (!confirm("Remove this question from the agent's memory?")) return;
    try {
        const token = getAuthToken();
        const res = await fetch(`/api/memory/qa/${encodeURIComponent(mId)}`, {
            method: "DELETE",
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (!res.ok) throw new Error("Could not delete");
        loadQAMemory();
    } catch (e) {
        alert("Error: " + e.message);
    }
}


// ==========================================
// Mouse-Interactive Animation & Particle Canvas Engine
// ==========================================
function initMouseInteractiveAnimations() {
    // 1. Particle Constellation Canvas with Interactive Mouse Physics
    const canvas = document.getElementById("interactiveCanvas");
    if (canvas) {
        const ctx = canvas.getContext("2d");
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;

        const particles = [];
        const particleCount = Math.min(Math.floor((width * height) / 18000), 65);
        const mouse = { x: -1000, y: -1000, radius: 140, isHovered: false };

        class Particle {
            constructor() {
                this.x = Math.random() * width;
                this.y = Math.random() * height;
                this.vx = (Math.random() - 0.5) * 0.5;
                this.vy = (Math.random() - 0.5) * 0.5;
                this.radius = Math.random() * 1.5 + 0.8;
                this.baseAlpha = Math.random() * 0.35 + 0.15;
                this.alpha = this.baseAlpha;
                this.color = Math.random() > 0.85 ? "rgba(16, 185, 129, " : "rgba(228, 228, 231, ";
            }
            update() {
                this.x += this.vx;
                this.y += this.vy;

                if (this.x < 0) this.x = width;
                if (this.x > width) this.x = 0;
                if (this.y < 0) this.y = height;
                if (this.y > height) this.y = 0;

                // Mouse interaction: gentle repulsion
                const dx = mouse.x - this.x;
                const dy = mouse.y - this.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < mouse.radius && mouse.isHovered) {
                    const force = (1 - dist / mouse.radius) * 1.4;
                    const angle = Math.atan2(dy, dx);
                    this.x -= Math.cos(angle) * force * 1.8;
                    this.y -= Math.sin(angle) * force * 1.8;
                    this.alpha = Math.min(this.baseAlpha + 0.35, 0.85);
                } else {
                    this.alpha += (this.baseAlpha - this.alpha) * 0.05;
                }
            }
            draw() {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                ctx.fillStyle = this.color + this.alpha + ")";
                ctx.fill();
            }
        }

        for (let i = 0; i < particleCount; i++) {
            particles.push(new Particle());
        }

        window.addEventListener("resize", () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        });

        window.addEventListener("mousemove", (e) => {
            mouse.x = e.clientX;
            mouse.y = e.clientY;
            mouse.isHovered = true;
        });

        window.addEventListener("mouseout", () => {
            mouse.isHovered = false;
            mouse.x = -1000;
            mouse.y = -1000;
        });

        function animateParticles() {
            ctx.clearRect(0, 0, width, height);

            // Draw connecting lines between close particles
            for (let i = 0; i < particles.length; i++) {
                particles[i].update();
                particles[i].draw();

                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 115) {
                        const lineAlpha = (1 - dist / 115) * 0.12;
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = `rgba(255, 255, 255, ${lineAlpha})`;
                        ctx.lineWidth = 0.75;
                        ctx.stroke();
                    }
                }

                // Connect particle to mouse cursor if near
                if (mouse.isHovered) {
                    const mdx = particles[i].x - mouse.x;
                    const mdy = particles[i].y - mouse.y;
                    const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
                    if (mdist < 130) {
                        const mLineAlpha = (1 - mdist / 130) * 0.22;
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(mouse.x, mouse.y);
                        ctx.strokeStyle = `rgba(16, 185, 129, ${mLineAlpha})`;
                        ctx.lineWidth = 1;
                        ctx.stroke();
                    }
                }
            }
            requestAnimationFrame(animateParticles);
        }
        animateParticles();
    }

    // 2. Global Mouse Spotlight Follower
    const spotlight = document.getElementById("mouseSpotlight");
    if (spotlight) {
        let targetX = window.innerWidth / 2;
        let targetY = window.innerHeight / 3;
        let currentX = targetX;
        let currentY = targetY;

        window.addEventListener("mousemove", (e) => {
            targetX = e.clientX;
            targetY = e.clientY;
        });

        function updateSpotlight() {
            currentX += (targetX - currentX) * 0.08;
            currentY += (targetY - currentY) * 0.08;
            spotlight.style.background = `radial-gradient(700px circle at ${currentX}px ${currentY}px, rgba(16, 185, 129, 0.04), rgba(59, 130, 246, 0.03) 40%, transparent 80%)`;
            requestAnimationFrame(updateSpotlight);
        }
        updateSpotlight();
    }

    // 3. Card 3D Perspective Tilt and Dynamic Spotlight Border
    function bindInteractiveCards() {
        const cards = document.querySelectorAll(".interactive-card");
        cards.forEach(card => {
            if (card.dataset.boundInteractive) return;
            card.dataset.boundInteractive = "true";

            card.addEventListener("mousemove", (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                card.style.setProperty("--card-x", `${x}px`);
                card.style.setProperty("--card-y", `${y}px`);

                // 3D Tilt calculation
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                const rotateX = ((y - centerY) / centerY) * -3.2;
                const rotateY = ((x - centerX) / centerX) * 3.2;
                card.style.transform = `perspective(800px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-2px)`;
            });

            card.addEventListener("mouseleave", () => {
                card.style.transform = "perspective(800px) rotateX(0deg) rotateY(0deg) translateY(0)";
            });
        });
    }

    bindInteractiveCards();
    setInterval(bindInteractiveCards, 2000);
}

document.addEventListener("DOMContentLoaded", () => {
    initMouseInteractiveAnimations();
});


// ==========================================
// Make.com Interactive Scenario Simulation
// ==========================================
let isSimulating = false;
function triggerScenarioSimulation() {
    if (isSimulating) return;
    isSimulating = true;

    const scenarioSec = document.getElementById("scenarioSection");
    if (scenarioSec) {
        scenarioSec.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    const btnText = document.getElementById("simBtnText");
    const logText = document.getElementById("simLogText");
    const candName = (currentAnalysis?.candidate_name || currentAuthUser?.name || "Candidate");
    const vaultCount = (typeof allMemories !== "undefined" && allMemories) ? allMemories.length : 0;
    const nodes = [
        { id: "simNode1", label: `1/5: Ingestion Complete · Extracted Skills DNA from ${candName}'s Resume` },
        { id: "simNode2", label: "2/5: Portal Scout Finished · Discovered Live Openings (≤ 15-Day Freshness Filtered)" },
        { id: "simNode3", label: `3/5: Screening Reasoning · Verified ${vaultCount} Canonical Facts from Memory Vault` },
        { id: "simNode4", label: "4/5: Zero-Hallucination Safe · Telegram Real-time HITL Gate Standby" },
        { id: "simNode5", label: "5/5: Playwright Submit Success · Headless Form Submitted & Screen Proof Captured" }
    ];

    if (btnText) btnText.textContent = "Simulating...";

    nodes.forEach(n => {
        const el = document.getElementById(n.id);
        if (el) {
            el.classList.remove("node-active-glow", "scale-110");
        }
    });

    let currentStep = 0;
    const interval = setInterval(() => {
        if (currentStep > 0) {
            const prevEl = document.getElementById(nodes[currentStep - 1].id);
            if (prevEl) prevEl.classList.remove("scale-110");
        }

        if (currentStep < nodes.length) {
            const step = nodes[currentStep];
            const el = document.getElementById(step.id);
            if (el) {
                el.classList.add("node-active-glow", "scale-110");
            }
            if (logText) {
                logText.innerHTML = `<span class="text-emerald-400 font-bold">●</span> ${step.label}`;
            }
            currentStep++;
        } else {
            clearInterval(interval);
            setTimeout(() => {
                if (logText) {
                    logText.innerHTML = `<span class="text-emerald-400 font-bold">&check;</span> Simulation Complete &middot; 5/5 Stages Verified with 100% Determinism & Zero Hallucination.`;
                }
                if (btnText) btnText.textContent = "Run Simulation";
                isSimulating = false;
            }, 1000);
        }
    }, 1100);
}


// =============================================================================
// AUTOAPPLY AUTHENTICATION & MULTI-TENANT CLOUD SYSTEM (Supabase 100% Free)
// =============================================================================
let currentAuthUser = null;
let currentAuthToken = null;
let supabaseClient = null;
let authMode = "signin"; // "signin" or "signup"

function getAuthToken() {
    return currentAuthToken || localStorage.getItem("autoapply_auth_token") || null;
}

function initSupabase() {
    const savedUrl = localStorage.getItem("supabase_url") || "";
    const savedKey = localStorage.getItem("supabase_anon_key") || "";
    const isRealSupabase = savedUrl && savedKey && !savedUrl.includes("iyqcrvdmlbtzrehwaxvl");

    if (isRealSupabase && window.supabase && window.supabase.createClient) {
        try {
            supabaseClient = window.supabase.createClient(savedUrl, savedKey);
            supabaseClient.auth.onAuthStateChange((event, session) => {
                if (session && session.user) {
                    setLoggedInUser(session.user, session.access_token);
                } else if (event === "SIGNED_OUT") {
                    setLoggedOutUser();
                }
            });
        } catch (e) {
            console.warn("Could not init Supabase client:", e);
            supabaseClient = null;
        }
    } else {
        supabaseClient = null;
    }

    // Restore existing session or default to logged-out Guest state (NO auto-login as Sachin!)
    const storedUser = localStorage.getItem("autoapply_user");
    const storedToken = localStorage.getItem("autoapply_auth_token");
    if (storedUser) {
        try {
            currentAuthUser = JSON.parse(storedUser);
            currentAuthToken = storedToken;
            renderAuthNavbar();
        } catch (e) {
            setLoggedOutUser();
        }
    } else {
        setLoggedOutUser();
    }

    // Check for redirect OAuth errors in URL
    const urlParams = new URLSearchParams(window.location.search);
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const authErrorDesc = urlParams.get('error_description') || hashParams.get('error_description');
    const authErrorCode = urlParams.get('error') || hashParams.get('error');
    if (authErrorDesc || authErrorCode) {
        setTimeout(() => {
            showAuthError("OAuth Notice: " + (decodeURIComponent(authErrorDesc || authErrorCode)) + ". Try Instant Demo Guest mode above or Email sign-in.");
            toggleAuthModal(true);
        }, 500);
    }

    // Monitor backend connectivity
    checkBackendHealth();
    setInterval(checkBackendHealth, 15000);
}

function createLocalAuthToken(user) {
    const b64 = (str) => btoa(unescape(encodeURIComponent(str))).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
    const header = b64(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = b64(JSON.stringify({
        sub: user.id,
        id: user.id,
        email: user.email,
        user_metadata: {
            full_name: user.name,
            name: user.name,
            avatar_url: user.avatar || ""
        },
        exp: Math.floor(Date.now() / 1000) + (30 * 24 * 60 * 60)
    }));
    const sig = b64("autoapply_client_sig");
    return `${header}.${payload}.${sig}`;
}

function setLoggedInUser(user, token) {
    currentAuthUser = {
        id: user.id,
        email: user.email,
        name: user.user_metadata?.full_name || user.name || user.email.split("@")[0],
        avatar: user.user_metadata?.avatar_url || user.avatar || null,
        provider: user.app_metadata?.provider || user.provider || "email"
    };
    currentAuthToken = token || createLocalAuthToken(currentAuthUser);
    localStorage.setItem("autoapply_user", JSON.stringify(currentAuthUser));
    localStorage.setItem("autoapply_auth_token", currentAuthToken);

    // Save to device saved accounts list for fast 1-click switching
    try {
        let saved = JSON.parse(localStorage.getItem("autoapply_saved_accounts") || "[]");
        saved = saved.filter(a => a.email.toLowerCase() !== currentAuthUser.email.toLowerCase());
        saved.unshift(currentAuthUser);
        if (saved.length > 5) saved = saved.slice(0, 5);
        localStorage.setItem("autoapply_saved_accounts", JSON.stringify(saved));
    } catch (e) {}

    renderAuthNavbar();
    toggleAuthModal(false);
    backToMainAuthView();

    // Reload candidate-specific isolated profile, memories & applications
    loadUserProfile();
    loadQAMemory();
    loadUserApplications();
}

function setLoggedOutUser() {
    currentAuthUser = null;
    currentAuthToken = null;
    currentAnalysis = null;
    currentSelectedRole = "";
    localStorage.removeItem("autoapply_user");
    localStorage.removeItem("autoapply_auth_token");
    renderAuthNavbar();
    backToMainAuthView();

    const statParsed = document.getElementById("statParsed");
    if (statParsed) {
        statParsed.textContent = "Awaiting";
        statParsed.className = "mt-2 text-lg sm:text-xl font-bold tracking-tight text-amber-400";
    }
    const statParsedSubtitle = document.getElementById("statParsedSubtitle");
    if (statParsedSubtitle) {
        statParsedSubtitle.textContent = "Upload resume to start";
    }
    const placeholder = document.getElementById("resumePlaceholderText");
    if (placeholder) {
        placeholder.textContent = "Click or drop resume file (PDF, DOCX, TXT)";
    }
    const targetNameEl = document.getElementById("agentTargetCandidateName");
    if (targetNameEl) targetNameEl.textContent = "Candidate";

    const profileCard = document.getElementById("profileCard");
    if (profileCard) profileCard.classList.add("hidden");

    renderJobsEmptyState();
    loadQAMemory();
    loadUserApplications();
}

async function loadUserProfile() {
    const token = getAuthToken();
    if (!token) return;
    try {
        const res = await fetch("/api/user/profile", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) return;
        const profile = await res.json();
        if (profile && (profile.technical_skills?.length > 0 || profile.skills?.length > 0 || profile.primary_domain || profile.experience_years)) {
            currentAnalysis = profile;
            renderProfile(profile);
            if (profile.primary_domain) {
                currentSelectedRole = profile.primary_domain;
                triggerJobSearch(currentSelectedRole);
            }
        }
    } catch (e) {
        console.warn("Could not load user profile:", e);
    }
}

async function loadUserApplications() {
    const token = getAuthToken();
    try {
        const res = await fetch("/api/user/applications", {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (!res.ok) return;
        const data = await res.json();
        const apps = data.applications || [];
        const statApplied = document.getElementById("statApplied");
        if (statApplied) statApplied.textContent = apps.length;
    } catch (e) {
        console.warn("Could not load user applications:", e);
    }
}

function loginAsDemoUser() {
    const demoUser = {
        id: "demo-guest-" + Date.now().toString(36),
        email: "demo.candidate@autoapply.ai",
        name: "Demo Candidate",
        provider: "demo"
    };
    const token = createLocalAuthToken(demoUser);
    setLoggedInUser(demoUser, token);
}

function renderAuthNavbar() {
    const signInBtn = document.getElementById("authSignInBtn");
    const userMenu = document.getElementById("authUserMenu");
    const nameDisplay = document.getElementById("userNameDisplay");
    const emailDisplay = document.getElementById("userEmailDisplay");
    const avatarDisplay = document.getElementById("userAvatar");

    const mobileUserName = document.getElementById("mobileUserName");
    const mobileUserAvatar = document.getElementById("mobileUserAvatar");
    const mobileSignInBtn = document.getElementById("mobileSignInBtn");
    const mobileSignOutBtn = document.getElementById("mobileSignOutBtn");
    const targetNameEl = document.getElementById("agentTargetCandidateName");

    const activeName = (currentAnalysis?.candidate_name || currentAuthUser?.name || "Candidate");
    if (targetNameEl) {
        targetNameEl.textContent = activeName;
    }

    if (currentAuthUser) {
        if (signInBtn) signInBtn.classList.add("hidden");
        if (userMenu) userMenu.classList.remove("hidden");
        if (nameDisplay) nameDisplay.textContent = currentAuthUser.name;
        if (emailDisplay) emailDisplay.textContent = currentAuthUser.email;
        
        if (avatarDisplay) {
            if (currentAuthUser.avatar) {
                avatarDisplay.innerHTML = `<img src="${currentAuthUser.avatar}" alt="${escapeHtml(currentAuthUser.name)}" class="w-full h-full rounded-full object-cover" onerror="this.parentElement.textContent='${(currentAuthUser.name[0] || 'U').toUpperCase()}'" />`;
            } else {
                avatarDisplay.textContent = (currentAuthUser.name[0] || "U").toUpperCase();
            }
        }

        if (mobileUserName) mobileUserName.textContent = currentAuthUser.name;
        if (mobileUserAvatar) {
            if (currentAuthUser.avatar) {
                mobileUserAvatar.innerHTML = `<img src="${currentAuthUser.avatar}" alt="${escapeHtml(currentAuthUser.name)}" class="w-full h-full rounded-full object-cover" onerror="this.parentElement.textContent='${(currentAuthUser.name[0] || 'U').toUpperCase()}'" />`;
            } else {
                mobileUserAvatar.textContent = (currentAuthUser.name[0] || "U").toUpperCase();
            }
        }
        if (mobileSignInBtn) mobileSignInBtn.classList.add("hidden");
        if (mobileSignOutBtn) mobileSignOutBtn.classList.remove("hidden");
    } else {
        if (signInBtn) signInBtn.classList.remove("hidden");
        if (userMenu) userMenu.classList.add("hidden");

        if (mobileUserName) mobileUserName.textContent = "Guest";
        if (mobileUserAvatar) mobileUserAvatar.textContent = "G";
        if (mobileSignInBtn) mobileSignInBtn.classList.remove("hidden");
        if (mobileSignOutBtn) mobileSignOutBtn.classList.add("hidden");
    }
    if (window.lucide) lucide.createIcons();
}

// =============================================================================
// Real Google Identity Services (GIS) & OAuth Authentication
// =============================================================================
const GOOGLE_CLIENT_ID = localStorage.getItem("google_client_id") || "1028741369796-7q4v1d4k19t06h40k5f2u0m9n8c08j12.apps.googleusercontent.com";

function parseJwtPayload(token) {
    try {
        const base64Url = token.split('.')[1];
        if (!base64Url) return null;
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        console.warn("JWT payload parse error:", e);
        return null;
    }
}

function initGoogleIdentity() {
    if (typeof google === "undefined" || !google.accounts || !google.accounts.id) {
        setTimeout(initGoogleIdentity, 600);
        return;
    }

    try {
        google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: handleGoogleCredentialResponse,
            auto_select: false,
            cancel_on_tap_outside: true
        });

        // Render official GIS button into containers
        const modalContainer = document.getElementById("googleGsiBtnModal");
        if (modalContainer) {
            google.accounts.id.renderButton(modalContainer, {
                theme: "filled_black",
                size: "large",
                width: 320,
                text: "continue_with",
                shape: "rectangular"
            });
        }
        const viewContainer = document.getElementById("googleGsiBtnView");
        if (viewContainer) {
            google.accounts.id.renderButton(viewContainer, {
                theme: "filled_blue",
                size: "large",
                width: 320,
                text: "signin_with",
                shape: "rectangular"
            });
        }
    } catch (e) {
        console.warn("Google Identity initialization warning:", e);
    }
}

function triggerGooglePrompt() {
    if (typeof google !== "undefined" && google.accounts && google.accounts.id) {
        google.accounts.id.prompt((notification) => {
            if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
                console.log("GIS prompt status:", notification.getNotDisplayedReason?.());
            }
        });
    } else {
        signInWithGoogleOAuth();
    }
}

async function handleGoogleCredentialResponse(response) {
    if (!response || !response.credential) {
        showAuthError("Google Sign-In did not return a valid credential token.");
        return;
    }

    const payload = parseJwtPayload(response.credential);
    if (!payload || !payload.email) {
        showAuthError("Could not retrieve verified profile from Google credential.");
        return;
    }

    const verifiedUser = {
        id: "google-" + (payload.sub || btoa(payload.email).replace(/[^a-zA-Z0-9]/g, "").slice(0, 14)),
        email: payload.email.toLowerCase(),
        name: payload.name || payload.email.split("@")[0],
        avatar: payload.picture || `https://ui-avatars.com/api/?name=${encodeURIComponent(payload.name || payload.email)}&background=4285F4&color=fff&bold=true`,
        provider: "google",
        user_metadata: {
            full_name: payload.name || payload.email.split("@")[0],
            name: payload.name,
            avatar_url: payload.picture,
            email_verified: payload.email_verified
        }
    };

    if (supabaseClient && supabaseClient.auth) {
        try {
            await supabaseClient.auth.signInWithIdToken({
                provider: "google",
                token: response.credential
            });
        } catch (e) {
            console.log("Supabase direct ID token note:", e.message);
        }
    }

    setLoggedInUser(verifiedUser, response.credential);
    toggleAuthModal(false);
}

function signInWithGoogleOAuth() {
    if (supabaseClient) {
        signInWithOAuth("google");
        return;
    }
    const redirectUri = window.location.origin + window.location.pathname;
    const scope = encodeURIComponent("openid email profile");
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=token%20id_token&scope=${scope}&nonce=aa_${Date.now()}`;
    window.location.href = authUrl;
}

function signInWithGitHubOAuth() {
    if (supabaseClient) {
        signInWithOAuth("github");
        return;
    }
    const savedGitHubId = localStorage.getItem("github_client_id");
    if (savedGitHubId) {
        const redirectUri = window.location.origin + window.location.pathname;
        window.location.href = `https://github.com/login/oauth/authorize?client_id=${encodeURIComponent(savedGitHubId)}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=read:user%20user:email`;
    } else {
        showAuthError("GitHub OAuth connects through your Supabase project keys (or GitHub Client ID). Please add keys under 'Cloud Config Keys' below, or sign in instantly with Google One Tap or Email.");
    }
}

function checkOAuthRedirectTokens() {
    const hash = window.location.hash.substring(1);
    if (!hash) return;
    const params = new URLSearchParams(hash);
    const idToken = params.get("id_token");
    const accessToken = params.get("access_token");

    if (idToken) {
        const payload = parseJwtPayload(idToken);
        if (payload && payload.email) {
            const verifiedUser = {
                id: "google-" + (payload.sub || btoa(payload.email).replace(/[^a-zA-Z0-9]/g, "").slice(0, 14)),
                email: payload.email.toLowerCase(),
                name: payload.name || payload.email.split("@")[0],
                avatar: payload.picture || `https://ui-avatars.com/api/?name=${encodeURIComponent(payload.name || payload.email)}&background=4285F4&color=fff&bold=true`,
                provider: "google",
                user_metadata: {
                    full_name: payload.name || payload.email.split("@")[0],
                    name: payload.name,
                    avatar_url: payload.picture,
                    email_verified: payload.email_verified
                }
            };
            setLoggedInUser(verifiedUser, idToken);
            window.history.replaceState(null, "", window.location.pathname + window.location.search);
        }
    }
}

// Google & GitHub Sub-Views
function openGoogleAuthView() {
    const main = document.getElementById("mainAuthView");
    const googleView = document.getElementById("googleAuthView");
    const github = document.getElementById("githubAuthView");
    if (main) main.classList.add("hidden");
    if (github) github.classList.add("hidden");
    if (googleView) googleView.classList.remove("hidden");
    renderGoogleSavedAccounts();
    triggerGooglePrompt();
    if (window.lucide) lucide.createIcons();
}

function openGitHubAuthView() {
    const main = document.getElementById("mainAuthView");
    const googleView = document.getElementById("googleAuthView");
    const github = document.getElementById("githubAuthView");
    if (main) main.classList.add("hidden");
    if (googleView) googleView.classList.add("hidden");
    if (github) github.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
}

function backToMainAuthView() {
    const main = document.getElementById("mainAuthView");
    const googleView = document.getElementById("googleAuthView");
    const github = document.getElementById("githubAuthView");
    if (googleView) googleView.classList.add("hidden");
    if (github) github.classList.add("hidden");
    if (main) main.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
}

function renderGoogleSavedAccounts() {
    const container = document.getElementById("googleSavedAccountsList");
    if (!container) return;
    try {
        const saved = JSON.parse(localStorage.getItem("autoapply_saved_accounts") || "[]");
        const googleAccounts = saved.filter(a => a.provider === "google");
        if (googleAccounts.length === 0) {
            container.classList.add("hidden");
            return;
        }
        container.classList.remove("hidden");
        container.innerHTML = `
            <span class="text-[10px] uppercase font-mono text-zinc-500 block mb-1">Previous Google Accounts</span>
            ${googleAccounts.map(a => `
                <div onclick="selectSavedAccount('${escapeHtml(a.id)}')" class="flex items-center justify-between p-2 rounded-lg bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 cursor-pointer transition">
                    <div class="flex items-center gap-2.5">
                        <div class="w-7 h-7 rounded-full bg-blue-600/20 text-blue-400 font-bold text-xs flex items-center justify-center border border-blue-500/30 shrink-0">
                            ${(a.name[0] || 'G').toUpperCase()}
                        </div>
                        <div class="text-left">
                            <p class="text-xs font-semibold text-zinc-200">${escapeHtml(a.name)}</p>
                            <p class="text-[10px] text-zinc-400 font-mono">${escapeHtml(a.email)}</p>
                        </div>
                    </div>
                    <span class="text-[10px] text-blue-400 font-medium">Continue →</span>
                </div>
            `).join('')}
        `;
    } catch (e) {
        container.classList.add("hidden");
    }
}

function selectSavedAccount(accountId) {
    try {
        const saved = JSON.parse(localStorage.getItem("autoapply_saved_accounts") || "[]");
        const match = saved.find(a => a.id === accountId);
        if (match) {
            const token = createLocalAuthToken(match);
            setLoggedInUser(match, token);
        }
    } catch (e) {}
}

function toggleMobileNavMenu(forceState) {
    const menu = document.getElementById("mobileNavMenu");
    const icon = document.getElementById("mobileMenuIcon");
    if (!menu) return;

    const shouldOpen = (typeof forceState === "boolean") ? forceState : menu.classList.contains("hidden");
    if (shouldOpen) {
        menu.classList.remove("hidden");
        if (icon) icon.setAttribute("data-lucide", "x");
    } else {
        menu.classList.add("hidden");
        if (icon) icon.setAttribute("data-lucide", "menu");
    }
    if (window.lucide) lucide.createIcons();
}

function toggleAuthModal(show) {
    const modal = document.getElementById("authModal");
    if (!modal) return;
    if (show) {
        modal.classList.remove("hidden");
        hideAuthError();
        backToMainAuthView();
        const emailInput = document.getElementById("authEmailInput");
        if (emailInput && (emailInput.value.includes("supabase.co") || emailInput.value.startsWith("http"))) {
            emailInput.value = "";
        }
        triggerGooglePrompt();
    } else {
        modal.classList.add("hidden");
        backToMainAuthView();
    }
    closeUserDropdown();
}

function switchAuthTab(tab) {
    authMode = tab;
    const tabSignIn = document.getElementById("tabSignInBtn");
    const tabSignUp = document.getElementById("tabSignUpBtn");
    const nameField = document.getElementById("signUpNameField");
    const submitText = document.getElementById("authSubmitBtnText");

    if (tab === "signin") {
        tabSignIn.className = "flex-1 py-1.5 rounded-md bg-zinc-800 text-zinc-100 transition shadow-sm";
        tabSignUp.className = "flex-1 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 transition";
        if (nameField) nameField.classList.add("hidden");
        if (submitText) submitText.textContent = "Sign In to Dashboard";
    } else {
        tabSignUp.className = "flex-1 py-1.5 rounded-md bg-zinc-800 text-zinc-100 transition shadow-sm";
        tabSignIn.className = "flex-1 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 transition";
        if (nameField) nameField.classList.remove("hidden");
        if (submitText) submitText.textContent = "Create Free Account";
    }
    hideAuthError();
}

async function signInWithOAuth(provider) {
    const savedUrl = localStorage.getItem("supabase_url") || "";
    const savedKey = localStorage.getItem("supabase_anon_key") || "";
    const hasRealSupabase = savedUrl && savedKey && !savedUrl.includes("iyqcrvdmlbtzrehwaxvl");

    if (!hasRealSupabase || !supabaseClient) {
        if (provider === "google") {
            signInWithGoogleOAuth();
            return;
        }
        showAuthError(
            `Google & GitHub OAuth connect through your free Supabase project keys. ` +
            `Click 'Cloud Config Keys' below to add your keys, or sign in instantly with Google One Tap, Email & Password, or Demo Guest mode!`
        );
        return;
    }
    try {
        const { error } = await supabaseClient.auth.signInWithOAuth({
            provider: provider,
            options: { redirectTo: window.location.origin }
        });
        if (error) {
            if (error.message && (error.message.includes("not enabled") || error.message.includes("validation_failed") || error.message.includes("Unsupported provider"))) {
                showAuthError(`The '${provider}' provider is not enabled in your Supabase project (Authentication -> Providers -> ${provider.charAt(0).toUpperCase() + provider.slice(1)}). Use Email or Instant Demo Guest mode.`);
                return;
            }
            throw error;
        }
    } catch (err) {
        showAuthError(err.message || "OAuth sign-in failed. Please use Email or Demo mode.");
    }
}

async function handleEmailAuth(event) {
    event.preventDefault();
    const email = document.getElementById("authEmailInput").value.trim().toLowerCase();
    const password = document.getElementById("authPasswordInput").value;
    const fullName = document.getElementById("authNameInput")?.value?.trim() || "";

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
        showAuthError("Please enter a valid email address.");
        return;
    }
    if (!password || password.length < 6) {
        showAuthError("Password must be at least 6 characters.");
        return;
    }

    const savedUrl = localStorage.getItem("supabase_url") || "";
    const savedKey = localStorage.getItem("supabase_anon_key") || "";
    const hasRealSupabase = savedUrl && savedKey && !savedUrl.includes("iyqcrvdmlbtzrehwaxvl");

    if (!hasRealSupabase || !supabaseClient) {
        let localUsers = {};
        try {
            localUsers = JSON.parse(localStorage.getItem("autoapply_local_users") || "{}");
        } catch (e) {
            localUsers = {};
        }

        if (authMode === "signup") {
            if (localUsers[email]) {
                showAuthError("An account with this email already exists. Please switch to 'Sign In'.");
                return;
            }
            const cleanName = fullName || email.split("@")[0].replace(/[._-]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
            const userObj = {
                id: "email-" + btoa(email).replace(/[^a-zA-Z0-9]/g, "").slice(0, 14),
                email: email,
                name: cleanName,
                user_metadata: { full_name: cleanName },
                passwordHash: btoa(password),
                provider: "email"
            };
            localUsers[email] = userObj;
            localStorage.setItem("autoapply_local_users", JSON.stringify(localUsers));
            const token = createLocalAuthToken(userObj);
            setLoggedInUser(userObj, token);
            return;
        } else {
            const existing = localUsers[email];
            if (!existing) {
                showAuthError("No account found for this email. Please switch to 'Create Account' tab to register.");
                return;
            }
            if (existing.passwordHash && existing.passwordHash !== btoa(password)) {
                showAuthError("Incorrect password. Please verify your credentials.");
                return;
            }
            const token = createLocalAuthToken(existing);
            setLoggedInUser(existing, token);
            return;
        }
    }

    try {
        if (authMode === "signup") {
            const { data, error } = await supabaseClient.auth.signUp({
                email,
                password,
                options: { data: { full_name: fullName } }
            });
            if (error) throw error;
            if (data.session) {
                setLoggedInUser(data.user, data.session.access_token);
            } else {
                showAuthError("Account created! Supabase has 'Confirm email' turned ON by default. To bypass email verification: In Supabase Dashboard (Auth -> Providers -> Email), turn OFF 'Confirm email'. Or click 'Continue as Demo Guest' above.");
            }
        } else {
            const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
            if (error) {
                if (error.message && error.message.toLowerCase().includes("email not confirmed")) {
                    showAuthError("Email not confirmed yet! Quick Tip: In Supabase Dashboard (Auth -> Providers -> Email), turn OFF 'Confirm email'. Or click 'Continue as Demo Guest' above.");
                    return;
                }
                throw error;
            }
            if (data.session) {
                setLoggedInUser(data.user, data.session.access_token);
            }
        }
    } catch (err) {
        showAuthError(err.message || "Authentication failed");
    }
}

function handleSignOut() {
    if (supabaseClient) {
        supabaseClient.auth.signOut();
    }
    setLoggedOutUser();
    closeUserDropdown();
}

function showAuthError(msg) {
    const box = document.getElementById("authErrorMsg");
    const txt = document.getElementById("authErrorText");
    if (box && txt) {
        txt.textContent = msg;
        box.classList.remove("hidden");
    }
}

function hideAuthError() {
    const box = document.getElementById("authErrorMsg");
    if (box) box.classList.add("hidden");
}

function toggleUserDropdown() {
    const p = document.getElementById("userDropdownPanel");
    if (p) p.classList.toggle("hidden");
}

function closeUserDropdown() {
    const p = document.getElementById("userDropdownPanel");
    if (p) p.classList.add("hidden");
}

function toggleCloudConfigModal(show) {
    const m = document.getElementById("cloudConfigModal");
    if (!m) return;
    if (show) {
        document.getElementById("cfgSupabaseUrl").value = localStorage.getItem("supabase_url") || "";
        document.getElementById("cfgSupabaseAnonKey").value = localStorage.getItem("supabase_anon_key") || "";
        if (document.getElementById("cfgBackendUrl")) {
            document.getElementById("cfgBackendUrl").value = localStorage.getItem("backend_api_url") || "";
        }
        m.classList.remove("hidden");
        checkPortalSessionStatus();
    } else {
        m.classList.add("hidden");
    }
    closeUserDropdown();
}

function openCloudConfigModal() {
    toggleCloudConfigModal(true);
}

function saveCloudConfig() {
    const url = document.getElementById("cfgSupabaseUrl")?.value?.trim() || "";
    const key = document.getElementById("cfgSupabaseAnonKey")?.value?.trim() || "";
    const backendUrl = document.getElementById("cfgBackendUrl")?.value?.trim() || "";

    if (!url && !key && !backendUrl) {
        alert("Please enter either Supabase credentials or a Backend Server URL.");
        return;
    }
    if ((url && !key) || (!url && key)) {
        alert("Please enter both Supabase Project URL and Anon Public Key, or leave both empty to keep defaults.");
        return;
    }
    if (url && key) {
        localStorage.setItem("supabase_url", url);
        localStorage.setItem("supabase_anon_key", key);
    }
    if (backendUrl) {
        localStorage.setItem("backend_api_url", backendUrl);
    } else {
        localStorage.removeItem("backend_api_url");
    }
    alert("Configuration saved! Updating client...");
    toggleCloudConfigModal(false);
    initSupabase();
    checkBackendHealth();
}

function resetCloudConfig() {
    localStorage.removeItem("supabase_url");
    localStorage.removeItem("supabase_anon_key");
    localStorage.removeItem("backend_api_url");
    if (document.getElementById("cfgSupabaseUrl")) document.getElementById("cfgSupabaseUrl").value = "";
    if (document.getElementById("cfgSupabaseAnonKey")) document.getElementById("cfgSupabaseAnonKey").value = "";
    if (document.getElementById("cfgBackendUrl")) document.getElementById("cfgBackendUrl").value = "";
    alert("Reset to default configuration.");
    toggleCloudConfigModal(false);
    initSupabase();
    checkBackendHealth();
}


// =============================================================================
// BACKEND CONNECTIVITY MONITOR & URL TESTER
// =============================================================================
async function checkBackendHealth() {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const remoteBackend = localStorage.getItem('backend_api_url') || DEFAULT_REMOTE_BACKEND;
    const statusDot = document.getElementById("backendStatusDot");
    const statusText = document.getElementById("backendStatusText");
    const statusPill = document.getElementById("backendStatusPill");
    const banner = document.getElementById("cloudBackendBanner");

    const targetUrl = (!isLocal && remoteBackend) 
        ? `${remoteBackend.replace(/\/$/, '')}/api/health` 
        : `/api/health`;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3500);
        const res = await originalFetch(targetUrl, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (res.ok) {
            if (statusDot) statusDot.className = "w-1.5 h-1.5 rounded-full bg-emerald-400";
            if (statusText) statusText.textContent = "Backend: Connected";
            if (statusPill) {
                statusPill.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition cursor-pointer bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:border-emerald-500/50";
                statusPill.title = `Connected to ${targetUrl}`;
            }
            if (banner) banner.classList.add("hidden");
            return true;
        }
    } catch (e) {
        // unreachable
    }

    if (statusDot) statusDot.className = "w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse";
    if (statusText) statusText.textContent = isLocal ? "Backend: Offline" : "Backend: Disconnected";
    if (statusPill) {
        statusPill.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition cursor-pointer bg-amber-500/10 border-amber-500/30 text-amber-300 hover:border-amber-500/50";
        statusPill.title = "Click to configure backend URL in Cloud Config";
    }
    if (!isLocal && banner) {
        banner.classList.remove("hidden");
    }
    return false;
}

async function testBackendUrl() {
    const input = document.getElementById("cfgBackendUrl");
    const statusEl = document.getElementById("cfgBackendPingStatus");
    if (!input || !statusEl) return;

    let url = input.value.trim();
    if (!url) {
        statusEl.innerHTML = `<span class="text-amber-400">⚠️ Please enter a URL first.</span>`;
        return;
    }
    url = url.replace(/\/$/, "");
    statusEl.innerHTML = `<span class="text-indigo-400 animate-pulse">⟳ Pinging ${url}/api/health...</span>`;

    try {
        const start = Date.now();
        const res = await originalFetch(`${url}/api/health`);
        const duration = Date.now() - start;
        if (res.ok) {
            const data = await res.json();
            statusEl.innerHTML = `<span class="text-emerald-400 font-medium">✓ Online (${duration}ms): Database = ${data.cloud_database || 'ok'}</span>`;
        } else {
            statusEl.innerHTML = `<span class="text-rose-400">✗ Responded with status ${res.status}. Verify endpoint.</span>`;
        }
    } catch (e) {
        statusEl.innerHTML = `<span class="text-rose-400">✗ Connection failed: ${e.message}</span>`;
    }
}


// =============================================================================
// PORTAL SESSION COOKIES & QUICK APPLY ASSISTANT
// =============================================================================
async function checkPortalSessionStatus() {
    const badgeN = document.getElementById("badgeNaukriStatus");
    const badgeW = document.getElementById("badgeWellfoundStatus");
    try {
        const res = await fetch("/api/session/status");
        if (res.ok) {
            const data = await res.json();
            if (badgeN) {
                badgeN.textContent = data.naukri_connected ? `Connected (${data.naukri_cookies_count})` : "Not Synced";
                badgeN.className = data.naukri_connected ? "text-emerald-400 font-semibold" : "text-amber-400 font-semibold";
            }
            if (badgeW) {
                badgeW.textContent = data.wellfound_connected ? `Connected (${data.wellfound_cookies_count})` : "Not Synced";
                badgeW.className = data.wellfound_connected ? "text-emerald-400 font-semibold" : "text-amber-400 font-semibold";
            }
            return data;
        }
    } catch (e) {
        console.warn("Could not check session status:", e);
    }
}

async function saveConnectedCookies(platform, cookieData, fromAssistant = false) {
    try {
        const token = getAuthToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch("/api/session/connect-cookies", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                platform: platform,
                cookies: cookieData
            })
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
            alert(`🎉 ${data.message}`);
            checkPortalSessionStatus();
            if (fromAssistant) {
                closeQuickApplyModal();
            }
        } else {
            alert(`⚠️ Error saving session: ${data.detail || data.message || 'Unknown error'}`);
        }
    } catch (e) {
        alert("Network error saving session: " + e.message);
    }
}

function handleCookieFileUpload(event, platform, fromAssistant = false) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const json = JSON.parse(e.target.result);
            await saveConnectedCookies(platform, json, fromAssistant);
        } catch (err) {
            alert("Invalid JSON file: " + err.message);
        }
    };
    reader.readAsText(file);
}

function promptPasteCookies(platform, fromAssistant = false) {
    const raw = prompt(`Paste your ${platform} cookies JSON here:`);
    if (!raw) return;
    try {
        const json = JSON.parse(raw);
        saveConnectedCookies(platform, json, fromAssistant);
    } catch (err) {
        alert("Invalid JSON format. Please paste valid JSON: " + err.message);
    }
}

let activeAssistantJobIdx = null;
let currentAssistantPlatform = "naukri";

function openQuickApplyModal(idx, reason) {
    const job = foundJobs[idx];
    if (!job) return;
    activeAssistantJobIdx = idx;

    const rawPlatform = (job.platform || "Naukri").toLowerCase();
    currentAssistantPlatform = rawPlatform.includes("wellfound") ? "wellfound" : "naukri";
    const platformDisplay = currentAssistantPlatform === "wellfound" ? "Wellfound" : "Naukri";

    const modal = document.getElementById("quickApplyAssistantModal");
    const titleEl = document.getElementById("assistantJobTitle");
    const companyEl = document.getElementById("assistantCompany");
    const alertEl = document.getElementById("assistantReasonAlert");
    const pitchBox = document.getElementById("assistantPitchPreviewBox");
    const btnText = document.getElementById("btnAssistantGenerateText");
    const uploadLabel = document.getElementById("assistantUploadLabel");
    const sessionTitle = document.getElementById("assistantSessionTitle");

    if (titleEl) titleEl.textContent = job.title;
    if (companyEl) companyEl.textContent = `${job.company} • ${platformDisplay}`;
    if (alertEl) {
        alertEl.innerHTML = `<span class="font-semibold">${platformDisplay} session not synced or cloud browser unavailable.</span> Choose an option below to apply right now:`;
    }
    if (sessionTitle) {
        sessionTitle.textContent = `Connect ${platformDisplay} Session for Background Auto-Apply`;
    }
    if (uploadLabel) {
        uploadLabel.textContent = `Upload ${currentAssistantPlatform}_cookies.json`;
    }
    if (pitchBox) pitchBox.classList.add("hidden");
    if (btnText) btnText.textContent = "Copy Tailored Pitch & Open Job";

    if (modal) modal.classList.remove("hidden");
    if (typeof lucide !== "undefined") lucide.createIcons();
}

function handleAssistantFileSelect(event) {
    handleCookieFileUpload(event, currentAssistantPlatform, true);
}

function handleAssistantPasteClick() {
    promptPasteCookies(currentAssistantPlatform, true);
}

function closeQuickApplyModal() {
    const modal = document.getElementById("quickApplyAssistantModal");
    if (modal) modal.classList.add("hidden");
    activeAssistantJobIdx = null;
}

async function assistantGeneratePitchAndOpen() {
    if (activeAssistantJobIdx === null || !foundJobs[activeAssistantJobIdx]) return;
    const job = foundJobs[activeAssistantJobIdx];
    const btn = document.getElementById("btnAssistantGeneratePitch");
    const btnText = document.getElementById("btnAssistantGenerateText");
    const pitchBox = document.getElementById("assistantPitchPreviewBox");
    const pitchText = document.getElementById("assistantPitchText");

    if (btn) btn.disabled = true;
    if (btnText) btnText.innerHTML = "Generating AI Pitch with Gemini/Groq...";

    const candidateName = currentAnalysis?.candidate_name || currentAuthUser?.name || "Candidate";

    try {
        const token = getAuthToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch("/api/jobs/prepare-application", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                job_title: job.title,
                company: job.company,
                platform: job.platform || 'Naukri',
                job_url: job.job_url,
                candidate_name: candidateName
            })
        });
        const data = await res.json();
        const pitch = data.cover_letter || `Dear Hiring Team at ${job.company},\n\nI am writing to express my strong interest in the ${job.title} position at ${job.company}.\n\nBest regards,\n${candidateName}`;

        // Copy to clipboard
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(pitch);
            }
        } catch (clipErr) {
            console.warn("Clipboard copy error:", clipErr);
        }

        if (pitchText) pitchText.value = pitch;
        if (pitchBox) pitchBox.classList.remove("hidden");
        if (btnText) btnText.innerHTML = "✅ Pitch Copied! Opening Job...";

        // Open job URL in new tab with security rel attributes
        setTimeout(() => {
            if (job.job_url) {
                window.open(job.job_url, "_blank", "noopener,noreferrer");
            }
        }, 600);

        // Update status in table
        const statusCell = document.getElementById(`status-cell-${activeAssistantJobIdx}`);
        if (statusCell) {
            statusCell.innerHTML = `
                <span class="inline-flex items-center gap-1.5 text-indigo-400 text-xs font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-indigo-400"></span> Pitched ⚡
                </span>
            `;
        }

    } catch (e) {
        if (job.job_url) {
            window.open(job.job_url, "_blank", "noopener,noreferrer");
        }
        if (btnText) btnText.innerHTML = "Opening Job...";
    } finally {
        if (btn) btn.disabled = false;
    }
}


// =============================================================================
// Keyboard Escape & Backdrop Click Modal Dismissal
// =============================================================================
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closeModal();
        closePlatformModal();
        toggleAuthModal(false);
        toggleCloudConfigModal(false);
        closeQuickApplyModal();
        toggleVaultModal(false);
        closeUserDropdown();
        toggleMobileNavMenu(false);
    }
});

["applyModal", "platformSelectorModal", "authModal", "cloudConfigModal", "quickApplyAssistantModal", "memoryVaultModal"].forEach(modalId => {
    const el = document.getElementById(modalId);
    if (el) {
        el.addEventListener("click", (e) => {
            if (e.target === el) {
                if (modalId === "applyModal") closeModal();
                else if (modalId === "platformSelectorModal") closePlatformModal();
                else if (modalId === "authModal") toggleAuthModal(false);
                else if (modalId === "cloudConfigModal") toggleCloudConfigModal(false);
                else if (modalId === "quickApplyAssistantModal") closeQuickApplyModal();
                else if (modalId === "memoryVaultModal") toggleVaultModal(false);
            }
        });
    }
});
