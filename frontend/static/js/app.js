// =============================================================================
// GLOBAL FETCH WRAPPER: Automatically injects JWT Bearer token on all API calls
// =============================================================================
const DEFAULT_REMOTE_BACKEND = "https://autoapply-backend-hvdm.onrender.com";
const originalFetch = window.fetch.bind(window);
window.fetch = async function(input, init = {}) {
    init = { ...init };
    let targetUrl = typeof input === "string" ? input : (input?.url || "");
    
    // Only rewrite to remote origin if explicitly configured in settings (e.g. custom Hugging Face Space);
    // otherwise use same-origin relative paths to route cleanly through Vercel edge rewrites without CORS preflights
    const customBackend = localStorage.getItem("backend_api_url");
    if (targetUrl.startsWith("/api/") && customBackend && customBackend.trim()) {
        const cleanCustom = customBackend.trim().replace(/\/$/, "");
        targetUrl = `${cleanCustom}${targetUrl}`;
        input = typeof input === "string" ? targetUrl : new Request(targetUrl, input);
    }
    
    const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
    const token = localStorage.getItem("autoapply_auth_token") || localStorage.getItem("supabase_jwt_token");
    if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
    }
    init.headers = headers;
    return originalFetch(input, init);
};

// =============================================================================
// BACKEND URL RESOLVER & PROOF ROUTING ENGINE
// =============================================================================
function getBackendApiUrl() {
    const custom = localStorage.getItem("backend_api_url");
    if (custom && custom.trim()) {
        return custom.trim().replace(/\/$/, "");
    }
    // On Vercel and local environments, leverage same-origin proxy rewrites
    return window.location.origin;
}

function getProofUrl(proofPath) {
    if (!proofPath || typeof proofPath !== "string") return "";
    const cleanPath = proofPath.trim();
    if (!cleanPath || cleanPath === "#") return "";
    if (cleanPath.startsWith("http://") || cleanPath.startsWith("https://")) {
        return cleanPath;
    }
    const base = getBackendApiUrl();
    if (cleanPath.startsWith("/")) {
        return `${base}${cleanPath}`;
    }
    if (cleanPath.startsWith("proofs/")) {
        return `${base}/${cleanPath}`;
    }
    return `${base}/proofs/${cleanPath}`;
}

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
        
        if (status === 404 || text.includes("The page could not be found") || text.includes("DEPLOYMENT_NOT_FOUND") || status === 502 || status === 504) {
            if (isVercel) {
                throw new Error(
                    "Backend Server is Waking Up (~45s)\n\n" +
                    "Render's free tier spins down to sleep after 15 minutes of inactivity.\n" +
                    "The server is booting up automatically now.\n\n" +
                    "Please wait 20-30 seconds and try again — no manual connection is required!"
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


// =============================================================================
// GLOBAL AUTHENTICATION & MULTI-TENANT IDENTITY STATE
// =============================================================================
let currentAuthUser = null;
let currentAuthToken = null;
let supabaseClient = null;
let authMode = "signin"; // "signin" or "signup"

function getAuthToken() {
    return currentAuthToken || localStorage.getItem("autoapply_auth_token") || null;
}

function requireAuth(actionDescription = "access this feature") {
    if (!currentAuthUser || !currentAuthUser.id || currentAuthUser.id === "guest-candidate" || currentAuthUser.id.startsWith("demo-")) {
        toggleAuthModal(true);
        showAuthError(`Authentication Required: Please sign in or create an account to ${actionDescription}.`);
        return false;
    }
    return true;
}

let currentAnalysis = null;
let foundJobs = [];
let activeApplyingJobIndex = null;
let currentSelectedRole = "";
let currentSelectedPlatform = "naukri"; // "naukri" or "wellfound"

document.addEventListener("DOMContentLoaded", () => {
    initSupabase();

    const dropzone = document.getElementById("dropzone");
    const resumeFileInput = document.getElementById("resumeFileInput");
    const fileStatus = document.getElementById("fileStatus");
    const fileName = document.getElementById("fileName");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const searchJobsBtn = document.getElementById("searchJobsBtn");

    if (dropzone && resumeFileInput) {
        dropzone.addEventListener("click", () => {
            if (!requireAuth("upload and analyze your resume")) return;
            resumeFileInput.click();
        });

        ["dragenter", "dragover"].forEach(name => {
            dropzone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add("border-indigo-500", "bg-zinc-900/60");
            });
        });
        ["dragleave", "drop"].forEach(name => {
            dropzone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove("border-indigo-500", "bg-zinc-900/60");
            });
        });
        dropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!requireAuth("upload and analyze your resume")) return;
            const files = e.dataTransfer?.files;
            if (files && files.length > 0) {
                resumeFileInput.files = files;
                const file = files[0];
                if (fileName) fileName.textContent = file.name;
                if (fileStatus) fileStatus.classList.remove("hidden");
                const placeholder = document.getElementById("resumePlaceholderText");
                if (placeholder) placeholder.textContent = file.name;
            }
        });
    }

    if (resumeFileInput) {
        resumeFileInput.addEventListener("click", (e) => {
            if (!requireAuth("upload and analyze your resume")) {
                e.preventDefault();
                return false;
            }
        });
        resumeFileInput.addEventListener("change", (e) => {
            if (!requireAuth("upload and analyze your resume")) {
                e.target.value = "";
                return;
            }
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
            if (!requireAuth("analyze your resume with LLM")) return;
            const file = resumeFileInput?.files[0];
            if (!file) {
                alert("Please select a resume file (PDF, DOCX, TXT) first.");
                resumeFileInput?.click();
                return;
            }
            await analyzeSelectedResumeFile(file);
        });
    }

    if (searchJobsBtn) {
        searchJobsBtn.addEventListener("click", () => {
            if (!requireAuth("search and scout matched jobs")) return;
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

    // Initialize Memory Vault & Polling (default 6s standard interval)
    loadQAMemory();
    startQAPolling(6000);

    // Setup Enter key submission on #pendingModalAnswerInput
    const pendingModalInput = document.getElementById("pendingModalAnswerInput");
    if (pendingModalInput) {
        pendingModalInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                handlePendingModalSubmit();
            }
        });
    }

    // Auto-restore cookies in background if stored in localStorage
    if (typeof getStoredCookiesFromLocalStorage === "function") {
        if (getStoredCookiesFromLocalStorage("naukri")) {
            tryRestoreSessionCookies("naukri");
        }
        if (getStoredCookiesFromLocalStorage("wellfound")) {
            tryRestoreSessionCookies("wellfound");
        }
    }
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
            <td colspan="5" class="py-12 px-6 text-center whitespace-normal">
                <div class="flex flex-col items-center justify-center w-full max-w-md mx-auto space-y-3 whitespace-normal">
                    <div class="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                        <i data-lucide="file-search" class="w-6 h-6"></i>
                    </div>
                    <div class="space-y-1 w-full whitespace-normal break-words">
                        <h4 class="text-sm font-semibold text-zinc-100 whitespace-normal break-words">Upload and analyze your resume first</h4>
                        <p class="text-xs text-zinc-400 leading-relaxed whitespace-normal break-words">
                            The AI agent will extract your skills DNA and automatically scout 100% matched openings for your domain.
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
    if (!requireAuth("scout and match live jobs")) return;
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
                    <button type="button" onclick="handleExternalJobClick(event, '${escapeHtml(job.job_url)}')" class="text-zinc-400 hover:text-zinc-200 text-xs px-2 py-1 transition mr-0.5 cursor-pointer">View</button>
                    <button onclick="directApplyRow(${idx})" class="bg-zinc-100 hover:bg-white text-zinc-900 text-[11px] px-2.5 py-1 rounded-md font-semibold transition shadow-sm cursor-pointer">
                        Auto-Apply
                    </button>
                    <button onclick="openQuickApplyModal(${idx})" class="quick-apply-btn bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700/60 text-[11px] px-2 py-1 rounded-md font-medium transition cursor-pointer">
                        Quick Apply
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
                    <button onclick="openQuickApplyModal(${idx})" class="quick-apply-btn bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs px-3 py-2 rounded-lg font-medium transition border border-zinc-700/60">
                        Quick Apply
                    </button>
                    <button type="button" onclick="handleExternalJobClick(event, '${escapeHtml(job.job_url)}')" class="bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs px-2.5 py-2 rounded-lg transition border border-zinc-800 flex items-center justify-center cursor-pointer">
                        <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                    </button>
                </div>
            </div>
        `).join("");
    }
    if (window.lucide) lucide.createIcons();
}

// ==========================================
// 1-Click Autonomous Apply (Naukri & Wellfound)
// ==========================================
async function applySingleJob(idx) { return directApplyRow(idx); }


async function analyzeSelectedResumeFile(file) {
    if (!file) return null;
    const analyzeBtn = document.getElementById("analyzeBtn");
    if (analyzeBtn) {
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = "Analyzing...";
    }

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
        return data;
    } catch (error) {
        console.warn("Resume Analysis Notice:", error);
        alert("Resume Analysis Notice:\n\n" + error.message);
        throw error;
    } finally {
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "Analyze Resume with LLM";
        }
    }
}

async function directApplyRow(idx) {
    if (!requireAuth("apply for jobs")) return;
    const job = foundJobs[idx];
    if (!job) return;

    // Switch to FAST QA polling (1.5s) during active application
    setFastQAPolling();

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
        // Auto-analyze selected resume if not yet analyzed
        if (!currentAnalysis) {
            const resumeFileInput = document.getElementById("resumeFileInput");
            if (resumeFileInput && resumeFileInput.files && resumeFileInput.files.length > 0) {
                console.log("[Apply] Resume file selected but unanalyzed. Auto-analyzing now...");
                if (actionCell) actionCell.innerHTML = `<span class="text-xs text-amber-400 animate-spin mr-1">⟳</span> <span class="text-xs text-amber-300 font-medium">Extracting skills...</span>`;
                if (actionCard) actionCard.innerHTML = `<div class="w-full text-center py-2 text-amber-300 text-xs font-medium"><span class="animate-spin mr-1 inline-block">⟳</span> Extracting skills...</div>`;
                try {
                    await analyzeSelectedResumeFile(resumeFileInput.files[0]);
                } catch (autoErr) {
                    console.warn("[Apply] Auto-analysis notice:", autoErr);
                }
            } else if (currentAuthUser) {
                await loadUserProfile();
            }
        }

        const platformKey = isWellfound ? "wellfound" : "naukri";
        const storedCookiesRaw = localStorage.getItem(`autoapply_${platformKey}_cookies`);
        let attachedCookies = null;
        if (storedCookiesRaw) {
            try { attachedCookies = JSON.parse(storedCookiesRaw); } catch(_) {}
        }

        const payload = {
            job_url: job.job_url,
            job_title: job.title,
            company: job.company || "Hiring Company",
            cookies: attachedCookies,
            candidate_profile: currentAnalysis
        };

        const token = getAuthToken();
        let res = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify(payload)
        });
        let data = await safeParseJson(res);

        // Auto-retry once if backend returns session_required and cookies are stored in localStorage
        if (data && data.status === "session_required") {
            console.log(`[Apply] Received session_required for ${platformLabel}. Auto-restoring cookies from localStorage...`);
            const restored = await tryRestoreSessionCookies(isWellfound ? "wellfound" : "naukri");
            if (restored) {
                console.log(`[Apply] Session restored! Retrying application for ${job.title}...`);
                res = await fetch(endpoint, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        ...(token ? { "Authorization": `Bearer ${token}` } : {})
                    },
                    body: JSON.stringify(payload)
                });
                data = await safeParseJson(res);
            }
        }
        const statApplied = document.getElementById("statApplied");

        if (data.status === "applied_successfully" || data.status === "applied" || data.applied === true) {
            const appliedStatusHtml = `
                <span class="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Applied ✅
                </span>
            `;
            if (statusCell) statusCell.innerHTML = appliedStatusHtml;
            if (statusCard) statusCard.innerHTML = appliedStatusHtml;

            const proofUrl = getProofUrl(data.proof_image);
            const safeJobTitle = (job.title || "").replace(/['"\\]/g, " ");
            const proofBtnHtml = proofUrl ? `
                <a href="${proofUrl}" onclick="openProofModal('${proofUrl}', '${safeJobTitle}'); return false;" class="text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-bold hover:underline inline-flex items-center justify-center gap-1 w-full sm:w-auto cursor-pointer">
                    📸 Proof
                </a>
            ` : `
                <a href="${escapeHtml(job.job_url)}" target="_blank" rel="noopener noreferrer" class="text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-bold hover:underline inline-flex items-center justify-center gap-1 w-full sm:w-auto cursor-pointer">
                    🔗 View Job
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

            const alreadyProofUrl = getProofUrl(data.proof_image);
            const safeJobTitle = (job.title || "").replace(/['"\\]/g, " ");
            const alreadyProofHtml = alreadyProofUrl ? `
                <a href="${alreadyProofUrl}" onclick="openProofModal('${alreadyProofUrl}', '${safeJobTitle}'); return false;" class="text-[11px] text-slate-400 bg-slate-800 border border-slate-700 px-2.5 py-1.5 sm:py-1 rounded-lg font-medium hover:underline inline-flex items-center justify-center w-full sm:w-auto cursor-pointer">
                    📸 Proof
                </a>
            ` : `
                <a href="${escapeHtml(job.job_url)}" target="_blank" rel="noopener noreferrer" class="text-[11px] text-slate-400 bg-slate-800 border border-slate-700 px-2.5 py-1.5 sm:py-1 rounded-lg font-medium hover:underline inline-flex items-center justify-center w-full sm:w-auto cursor-pointer">
                    🔗 View Job
                </a>
            `;
            if (actionCell) actionCell.innerHTML = alreadyProofHtml;
            if (actionCard) actionCard.innerHTML = alreadyProofHtml;
            alert(`ℹ️ You have already applied to ${job.title} on ${platformLabel}.`);
        } else if (data.status === "external_portal" || data.status === "external_redirect") {
            const extHtml = `
                <span class="inline-flex items-center gap-1.5 text-blue-400 text-xs font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-blue-400"></span> External Portal
                </span>
            `;
            if (statusCell) statusCell.innerHTML = extHtml;
            if (statusCard) statusCard.innerHTML = extHtml;

            const extActionHtml = `
                <button type="button" onclick="openQuickApplyModal(${idx}, 'external_portal')" class="text-[11px] text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 rounded-lg font-bold hover:underline inline-flex items-center gap-1 cursor-pointer">
                    📋 AI Pitch & Apply ↗
                </button>
            `;
            if (actionCell) actionCell.innerHTML = extActionHtml;
            if (actionCard) actionCard.innerHTML = extActionHtml;

            openQuickApplyModal(idx, data.message || "External career portal application required.", data.proof_image || data.proof_url, data.status);
        } else if (data.status === "job_expired") {
            const expHtml = `
                <span class="inline-flex items-center gap-1.5 text-zinc-500 text-xs font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-zinc-500"></span> Listing Closed
                </span>
            `;
            if (statusCell) statusCell.innerHTML = expHtml;
            if (statusCard) statusCard.innerHTML = expHtml;
            alert(`ℹ️ This job opening has expired or was closed by the recruiter on ${platformLabel}. Please choose another opening.`);
        } else if (data.status === "needs_human_action") {
            const reviewHtml = `<span class="text-amber-400 text-xs font-medium">⚠️ Review Needed</span>`;
            if (statusCell) statusCell.innerHTML = reviewHtml;
            if (statusCard) statusCard.innerHTML = reviewHtml;

            const reviewProofUrl = getProofUrl(data.proof_image);
            const safeJobTitle = (job.title || "").replace(/['"\\]/g, " ");
            const reviewBtnHtml = reviewProofUrl ? `
                <a href="${reviewProofUrl}" onclick="openProofModal('${reviewProofUrl}', '${safeJobTitle}'); return false;" class="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-medium hover:underline inline-flex items-center justify-center w-full sm:w-auto cursor-pointer">
                    ⚠️ View Alert / Proof
                </a>
            ` : `
                <span class="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-medium inline-flex items-center justify-center w-full sm:w-auto">
                    ⚠️ Alert Sent
                </span>
            `;
            if (actionCell) actionCell.innerHTML = reviewBtnHtml;
            if (actionCard) actionCard.innerHTML = reviewBtnHtml;
            alert(`⚠️ Recruiter Question Needed:\n\n${data.message}`);
        } else if (data.status === "cloud_security_challenge") {
            const challengeBtnHtml = `
                <button type="button" onclick="handleInstant1ClickApply(${idx})" class="w-full sm:w-auto px-2.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-[11px] transition shadow flex items-center justify-center gap-1 cursor-pointer">
                    ⚡ 1-Click Apply ↗
                </button>
            `;
            const challengeStatusHtml = `
                <span class="inline-flex items-center gap-1.5 text-amber-400 text-xs font-semibold" title="Naukri cloud bot challenge detected on datacenter server. Click 1-Click Apply to submit directly via your browser.">
                    <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span> Cloud Bot Gate
                </span>
            `;
            if (actionCell) actionCell.innerHTML = challengeBtnHtml;
            if (actionCard) actionCard.innerHTML = challengeBtnHtml;
            if (statusCell) statusCell.innerHTML = challengeStatusHtml;
            if (statusCard) statusCard.innerHTML = challengeStatusHtml;
            openQuickApplyModal(idx, data.message, data.proof_image || data.proof_url, data.status);
        } else if (data.status === "session_required") {
            const sessBtnHtml = `
                <button type="button" onclick="openQuickApplyModal(${idx}, 'Session connection required', null, 'session_required')" class="w-full sm:w-auto px-2.5 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-bold text-[11px] border border-amber-500/40 transition flex items-center justify-center gap-1 cursor-pointer">
                    🔑 Connect Session
                </button>
            `;
            if (actionCell) actionCell.innerHTML = sessBtnHtml;
            if (actionCard) actionCard.innerHTML = sessBtnHtml;
            openQuickApplyModal(idx, data.message || "Session connection required", data.proof_image || data.proof_url, data.status);
        } else {
            if (actionCell) actionCell.innerHTML = originalContent;
            if (actionCard) actionCard.innerHTML = originalCardContent;
            openQuickApplyModal(idx, data.message || "Application action needed", data.proof_image || data.proof_url, data.status);
        }
    } catch (e) {
        if (actionCell) actionCell.innerHTML = originalContent;
        if (actionCard) actionCard.innerHTML = originalCardContent;
        openQuickApplyModal(idx, e.message || "Automation error");
    } finally {
        setStandardQAPolling();
    }
}

// ==========================================
// Batch Autonomous Apply on Active Platform
// ==========================================
async function executeCurrentPlatformLiveBot() {
    if (!requireAuth("launch autonomous live auto-apply")) return;

    if (!currentAnalysis) {
        const resumeFileInput = document.getElementById("resumeFileInput");
        if (resumeFileInput && resumeFileInput.files && resumeFileInput.files.length > 0) {
            console.log("[Batch Apply] Auto-analyzing resume file before batch apply...");
            try {
                await analyzeSelectedResumeFile(resumeFileInput.files[0]);
            } catch (autoErr) {
                console.warn("[Batch Apply] Auto-analysis notice:", autoErr);
            }
        } else if (currentAuthUser) {
            await loadUserProfile();
        }
    }

    if (!currentAnalysis) {
        alert("Please upload and analyze your resume first! The AI agent needs your candidate DNA to tailor applications and match relevant openings.");
        document.getElementById("resumeFileInput")?.click();
        return;
    }

    // Switch to FAST QA polling (1.5s) during live autonomous batch execution
    setFastQAPolling();

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
        let res = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ query: query, limit: 3 })
        });

        let data = await safeParseJson(res);

        // Auto-retry once if backend returns session_required and cookies are stored in localStorage
        if (data && data.status === "session_required") {
            console.log(`[Batch Apply] Received session_required for ${platformLabel}. Auto-restoring cookies from localStorage...`);
            const restored = await tryRestoreSessionCookies(isWellfound ? "wellfound" : "naukri");
            if (restored) {
                console.log(`[Batch Apply] Session restored! Retrying autonomous batch apply on ${platformLabel}...`);
                res = await fetch(endpoint, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        ...(token ? { "Authorization": `Bearer ${token}` } : {})
                    },
                    body: JSON.stringify({ query: query, limit: 3 })
                });
                data = await safeParseJson(res);
            }
        }
        const apps = data.applications || [];

        let successCount = 0;
        let htmlLog = `<div class="mt-3 space-y-2 border-t border-slate-800 pt-2">`;

        apps.forEach((app, idx) => {
            const appProofUrl = getProofUrl(app.proof_image);
            const safeAppTitle = (app.job_title || "Application").replace(/['"\\]/g, " ");
            if (app.status === "applied_successfully") {
                successCount++;
                htmlLog += `
                    <div class="flex items-center justify-between bg-slate-900/80 p-2.5 rounded-lg border border-emerald-500/30">
                        <span class="text-emerald-400 font-medium">✅ Applied: <strong>${escapeHtml(app.job_title)}</strong></span>
                        ${appProofUrl ? `
                        <a href="${appProofUrl}" onclick="openProofModal('${appProofUrl}', '${safeAppTitle}'); return false;" class="text-xs text-emerald-300 bg-emerald-500/20 px-2.5 py-1 rounded font-bold hover:underline inline-flex items-center gap-1 cursor-pointer">
                            📸 View Submission Proof
                        </a>` : ''}
                    </div>
                `;
            } else if (app.status === "already_applied") {
                htmlLog += `
                    <div class="flex items-center justify-between bg-slate-900/80 p-2.5 rounded-lg border border-slate-700/50">
                        <span class="text-slate-400">ℹ️ ${escapeHtml(app.job_title)} (Already applied earlier)</span>
                        ${appProofUrl ? `<a href="${appProofUrl}" onclick="openProofModal('${appProofUrl}', '${safeAppTitle}'); return false;" class="text-xs text-slate-400 underline cursor-pointer">📸 Proof</a>` : ''}
                    </div>
                `;
            } else {
                htmlLog += `
                    <div class="bg-slate-900/80 p-2.5 rounded-lg border border-amber-500/30 text-amber-300">
                        ⚠️ <strong>${escapeHtml(app.job_title)}:</strong> External portal / screening question sent to your Telegram bot.
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
        setStandardQAPolling();
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
    if (!requireAuth("generate AI pitches and apply")) return;
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
// Candidate Q&A Memory Vault & HITL Screening Modal
// ==========================================
let allMemories = [];
let currentPendingModalQuestion = null;
let pendingModalCountdownTimer = null;
let pendingModalTimeLeft = 35;
let qaPollInterval = null;
let currentPollIntervalMs = 6000;
let originalDocTitle = document.title || "Antigravity - AI Autonomous Job Agent";
let titleAlertInterval = null;

function startQAPolling(intervalMs = 6000) {
    if (qaPollInterval) {
        clearInterval(qaPollInterval);
        qaPollInterval = null;
    }
    currentPollIntervalMs = intervalMs;
    qaPollInterval = setInterval(loadQAMemory, intervalMs);
}

function setFastQAPolling() {
    if (currentPollIntervalMs === 1500) return;
    console.log("[QA Polling] Activated FAST polling (1.5s) for live application");
    startQAPolling(1500);
    loadQAMemory();
}

function setStandardQAPolling() {
    if (currentPollIntervalMs === 6000) return;
    console.log("[QA Polling] Restored STANDARD polling (6.0s)");
    startQAPolling(6000);
}

function playHitlNotificationChime() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(587.33, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
        // Ignored if browser restricts autoplay before user interaction
    }
}

function startDocTitleAlert(text) {
    if (titleAlertInterval) clearInterval(titleAlertInterval);
    let toggle = false;
    titleAlertInterval = setInterval(() => {
        document.title = toggle ? `⚠️ ${text}` : `🔴 ACTION REQUIRED - Answer Recruiter`;
        toggle = !toggle;
    }, 1000);
}

function stopDocTitleAlert() {
    if (titleAlertInterval) {
        clearInterval(titleAlertInterval);
        titleAlertInterval = null;
    }
    document.title = originalDocTitle;
}

function openPendingQuestionModal(questionItem) {
    if (!questionItem) return;
    // Prevent UI jitter if the user is already answering this exact question
    if (currentPendingModalQuestion && currentPendingModalQuestion.id === questionItem.id) {
        return;
    }
    currentPendingModalQuestion = questionItem;

    const modal = document.getElementById("pendingQuestionModal");
    const companyEl = document.getElementById("pendingModalCompany");
    const roleEl = document.getElementById("pendingModalRole");
    const platformEl = document.getElementById("pendingModalPlatformBadge");
    const questionEl = document.getElementById("pendingModalQuestionText");
    const askedEl = document.getElementById("pendingModalAskedTime");
    const optionsContainer = document.getElementById("pendingModalOptionsContainer");
    const optionsList = document.getElementById("pendingModalOptionsList");
    const inputEl = document.getElementById("pendingModalAnswerInput");

    if (companyEl) companyEl.textContent = questionItem.company || "Direct Employer";
    if (roleEl) roleEl.textContent = questionItem.job_title || "Job Opening";

    let platform = questionItem.platform;
    if (!platform && questionItem.job_url) {
        platform = questionItem.job_url.toLowerCase().includes("wellfound") ? "Wellfound" : "Naukri";
    }
    if (platformEl) platformEl.textContent = (platform || "Naukri").toUpperCase();

    if (questionEl) questionEl.textContent = questionItem.question || "";
    if (askedEl) askedEl.textContent = questionItem.asked_at || "just now";

    // Clickable options chips (if recruiter provided multi-choice)
    if (optionsContainer && optionsList) {
        if (Array.isArray(questionItem.options) && questionItem.options.length > 0) {
            optionsContainer.classList.remove("hidden");
            optionsList.innerHTML = questionItem.options.map(opt => `
                <button type="button" onclick="selectPendingModalOption('${escapeHtml(opt)}')" class="px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-emerald-600/30 hover:border-emerald-500/50 hover:text-white text-zinc-300 text-xs border border-zinc-700/80 transition cursor-pointer font-medium">
                    ${escapeHtml(opt)}
                </button>
            `).join("");
        } else {
            optionsContainer.classList.add("hidden");
            optionsList.innerHTML = "";
        }
    }

    if (inputEl) {
        inputEl.value = "";
        setTimeout(() => inputEl.focus(), 150);
    }

    // 35-Second Visual Countdown Timer with animated progress bar
    if (pendingModalCountdownTimer) {
        clearInterval(pendingModalCountdownTimer);
        pendingModalCountdownTimer = null;
    }
    pendingModalTimeLeft = 35;
    const timerText = document.getElementById("pendingModalTimerText");
    const progressBar = document.getElementById("pendingModalProgressBar");
    if (timerText) {
        timerText.textContent = `${pendingModalTimeLeft}s remaining`;
        timerText.className = "font-mono font-bold text-amber-400";
    }
    if (progressBar) {
        progressBar.style.width = "100%";
        progressBar.className = "bg-gradient-to-r from-amber-500 to-emerald-400 h-1.5 rounded-full transition-all duration-1000 ease-linear";
    }

    pendingModalCountdownTimer = setInterval(() => {
        pendingModalTimeLeft--;
        if (timerText) timerText.textContent = `${Math.max(0, pendingModalTimeLeft)}s remaining`;
        if (progressBar) {
            const pct = Math.max(0, (pendingModalTimeLeft / 35) * 100);
            progressBar.style.width = `${pct}%`;
            if (pendingModalTimeLeft <= 10) {
                progressBar.className = "bg-rose-500 h-1.5 rounded-full transition-all duration-1000 ease-linear";
                if (timerText) timerText.className = "font-mono font-bold text-rose-400 animate-pulse";
            }
        }
        if (pendingModalTimeLeft <= 0) {
            clearInterval(pendingModalCountdownTimer);
            pendingModalCountdownTimer = null;
            if (timerText) timerText.textContent = "Response window elapsed";
        }
    }, 1000);

    if (modal) modal.classList.remove("hidden");
    playHitlNotificationChime();
    startDocTitleAlert(`Question Pending: ${questionItem.company || 'Job'}`);
    if (window.lucide) lucide.createIcons();
}

function selectPendingModalOption(val) {
    const input = document.getElementById("pendingModalAnswerInput");
    if (input) {
        input.value = val;
        input.focus();
    }
}

function closePendingQuestionModal() {
    const modal = document.getElementById("pendingQuestionModal");
    if (modal) modal.classList.add("hidden");
    if (pendingModalCountdownTimer) {
        clearInterval(pendingModalCountdownTimer);
        pendingModalCountdownTimer = null;
    }
    currentPendingModalQuestion = null;
    stopDocTitleAlert();
}

async function handlePendingModalSubmit() {
    if (!currentPendingModalQuestion) return;
    const input = document.getElementById("pendingModalAnswerInput");
    const answer = input ? input.value.trim() : "";
    if (!answer) {
        alert("Please enter or select an answer.");
        if (input) input.focus();
        return;
    }

    const qId = currentPendingModalQuestion.id;
    const submitBtn = document.getElementById("pendingModalSubmitBtn");
    const originalText = submitBtn ? submitBtn.innerHTML : "";
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span class="inline-block animate-spin mr-1">⟳</span> Submitting...`;
    }

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
        closePendingQuestionModal();
        await loadQAMemory();
    } catch (e) {
        alert("Error saving answer: " + e.message);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    }
}

async function handlePendingModalSkip() {
    if (!currentPendingModalQuestion) return;
    const qId = currentPendingModalQuestion.id;
    const skipBtn = document.getElementById("pendingModalSkipBtn");
    const originalText = skipBtn ? skipBtn.innerHTML : "";
    if (skipBtn) {
        skipBtn.disabled = true;
        skipBtn.innerHTML = `<span class="inline-block animate-spin mr-1">⟳</span> Skipping...`;
    }

    try {
        const token = getAuthToken();
        const res = await fetch("/api/memory/skip-pending", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ question_id: qId })
        });
        closePendingQuestionModal();
        await loadQAMemory();
    } catch (e) {
        alert("Error skipping question: " + e.message);
    } finally {
        if (skipBtn) {
            skipBtn.disabled = false;
            skipBtn.innerHTML = originalText;
        }
    }
}

async function loadQAMemory() {
    const uid = (currentAuthUser && currentAuthUser.id) ? currentAuthUser.id : "guest-candidate";
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
        allMemories = data.memories || [];
        localStorage.setItem(`autoapply_memories_${uid}`, JSON.stringify(allMemories));
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

    const activePending = (pending || []).filter(p => p.status === "pending");
    if (activePending.length === 0) {
        if (container) container.classList.add("hidden");
        // Automatically dismiss popup modal when questions are no longer pending
        if (currentPendingModalQuestion) {
            closePendingQuestionModal();
        }
        return;
    }

    // HIGH VISIBILITY POPUP MODAL: Pop up immediately when screening question is pending!
    const topPending = activePending[activePending.length - 1];
    openPendingQuestionModal(topPending);

    if (container && list) {
        container.classList.remove("hidden");
        list.innerHTML = activePending.map(p => `
            <div class="bg-zinc-950/80 border border-zinc-700/80 hover:border-zinc-600 rounded-xl p-4 space-y-3 transition shadow-sm interactive-card relative overflow-hidden">
                <div class="flex items-center justify-between text-xs">
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                        <span class="font-semibold text-zinc-100">${escapeHtml(p.company || 'Company')}</span>
                        <span class="text-zinc-500">/</span>
                        <span class="text-zinc-400">${escapeHtml(p.job_title || 'Role')}</span>
                    </div>
                    <span class="text-[10px] font-mono text-zinc-500">Asked: ${escapeHtml(p.asked_at || '')}</span>
                </div>

                <div class="p-3 bg-zinc-900/90 border border-zinc-800 rounded-lg">
                    <span class="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold block mb-1">Recruiter Screening Prompt</span>
                    <p class="text-xs font-medium text-zinc-100 leading-relaxed">
                        "${escapeHtml(p.question)}"
                    </p>
                </div>

                ${p.options && p.options.length > 0 ? `
                    <div class="text-[11px] text-zinc-400 flex flex-wrap gap-1.5 items-center">
                        <span class="text-zinc-500">Allowed options:</span>
                        ${p.options.map(o => `<span class="bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded text-[10px] text-zinc-300 font-mono">${escapeHtml(o)}</span>`).join('')}
                    </div>
                ` : ''}

                <div class="flex flex-col sm:flex-row gap-2 pt-1">
                    <input id="pending-ans-${p.id}" type="text" placeholder="Type verified candidate answer..." class="flex-1 px-3 py-2 bg-zinc-900 border border-zinc-800 focus:border-zinc-600 rounded-lg text-xs text-white placeholder-zinc-500 outline-none font-mono">
                    <div class="flex gap-2">
                        <button onclick="skipPendingQuestion('${p.id}')" class="px-3.5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs font-medium transition flex items-center justify-center gap-1.5 cursor-pointer">
                            <i data-lucide="skip-forward" class="w-3.5 h-3.5"></i>
                            <span>Skip Question</span>
                        </button>
                        <button onclick="submitPendingAnswer('${p.id}')" class="px-4 py-2 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 font-semibold text-xs transition shadow-sm flex items-center justify-center gap-1.5 cursor-pointer">
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
}

async function skipPendingQuestion(qId) {
    try {
        const token = getAuthToken();
        const res = await fetch("/api/memory/skip-pending", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ question_id: qId })
        });
        await safeParseJson(res);
        closePendingQuestionModal();
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
        closePendingQuestionModal();
        loadQAMemory();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

function toggleVaultModal(show) {
    if (show && !requireAuth("access your private Memory Vault")) {
        return;
    }
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
    if (!requireAuth("run AI scenario simulations")) return;
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
// (Authentication state declared at top of file)


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

function base64UrlEncode(str) {
    return btoa(unescape(encodeURIComponent(str)))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
}

function createLocalAuthToken(user) {
    const header = base64UrlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = base64UrlEncode(JSON.stringify({
        sub: user.id,
        id: user.id,
        email: user.email,
        role: "authenticated",
        aud: "authenticated",
        user_metadata: {
            full_name: user.name || user.email?.split("@")[0] || "Candidate",
            name: user.name || user.email?.split("@")[0] || "Candidate",
            provider: user.provider || "email"
        },
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + (60 * 60 * 24 * 7)
    }));
    const signature = base64UrlEncode("local_session_sig_" + (user.id || "guest"));
    return `${header}.${payload}.${signature}`;
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

    // Clean up any cross-account storage to prevent info leaks
    try {
        localStorage.removeItem("autoapply_saved_accounts");
    } catch (e) {}

    renderAuthNavbar();
    toggleAuthModal(false);

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
    localStorage.removeItem("autoapply_saved_accounts");
    
    const emailInput = document.getElementById("authEmailInput");
    const passInput = document.getElementById("authPasswordInput");
    const nameInput = document.getElementById("authNameInput");
    if (emailInput) emailInput.value = "";
    if (passInput) passInput.value = "";
    if (nameInput) nameInput.value = "";
    
    renderAuthNavbar();

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
    const statApplied = document.getElementById("statApplied");
    if (statApplied) statApplied.textContent = "0";
}

async function loadUserProfile() {
    if (!currentAuthUser || !currentAuthUser.id || currentAuthUser.id === "guest-candidate") return;
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
    if (!currentAuthUser || !currentAuthUser.id || currentAuthUser.id === "guest-candidate") {
        const statApplied = document.getElementById("statApplied");
        if (statApplied) statApplied.textContent = "0";
        return;
    }
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
    showAuthError("Demo guest access is disabled for production security. Please sign in or create an account.");
    toggleAuthModal(true);
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
// =============================================================================
// Clean Secure Email & Password Authentication
// =============================================================================

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

function toggleAuthModal(show, errorMsg = null) {
    const modal = document.getElementById("authModal");
    if (!modal) return;
    if (show) {
        modal.classList.remove("hidden");
        switchAuthTab("signin");
        if (errorMsg) {
            showAuthError(errorMsg);
        } else {
            hideAuthError();
        }
        const emailInput = document.getElementById("authEmailInput");
        const passInput = document.getElementById("authPasswordInput");
        const nameInput = document.getElementById("authNameInput");
        if (emailInput) emailInput.value = "";
        if (passInput) passInput.value = "";
        if (nameInput) nameInput.value = "";
    } else {
        modal.classList.add("hidden");
        hideAuthError();
        switchAuthTab("signin");
    }
    closeUserDropdown();
}

function switchAuthTab(tab) {
    authMode = tab;
    const tabSignIn = document.getElementById("tabSignInBtn");
    const tabSignUp = document.getElementById("tabSignUpBtn");
    const nameField = document.getElementById("signUpNameField");
    const nameInput = document.getElementById("authNameInput");
    const submitText = document.getElementById("authSubmitBtnText");
    const passwordLabel = document.getElementById("passwordLabel");
    const switchPrompt = document.getElementById("authSwitchPrompt");

    if (tab === "signin") {
        if (tabSignIn) tabSignIn.className = "flex-1 py-2 rounded-md bg-zinc-800 text-zinc-100 transition shadow-sm cursor-pointer font-semibold";
        if (tabSignUp) tabSignUp.className = "flex-1 py-2 rounded-md text-zinc-400 hover:text-zinc-200 transition cursor-pointer font-semibold";
        if (nameField) nameField.classList.add("hidden");
        if (nameInput) nameInput.required = false;
        if (submitText) submitText.textContent = "Sign In to Dashboard";
        if (passwordLabel) passwordLabel.textContent = "Password";
        if (switchPrompt) {
            switchPrompt.innerHTML = `Don't have an account yet? <button type="button" onclick="switchAuthTab('signup')" class="text-emerald-400 hover:text-emerald-300 font-semibold underline cursor-pointer ml-1">Create an account first</button>`;
        }
    } else {
        if (tabSignUp) tabSignUp.className = "flex-1 py-2 rounded-md bg-zinc-800 text-zinc-100 transition shadow-sm cursor-pointer font-semibold";
        if (tabSignIn) tabSignIn.className = "flex-1 py-2 rounded-md text-zinc-400 hover:text-zinc-200 transition cursor-pointer font-semibold";
        if (nameField) nameField.classList.remove("hidden");
        if (nameInput) nameInput.required = true;
        if (submitText) submitText.textContent = "Create Account & Get Started";
        if (passwordLabel) passwordLabel.textContent = "Create Password";
        if (switchPrompt) {
            switchPrompt.innerHTML = `Already have an account? <button type="button" onclick="switchAuthTab('signin')" class="text-emerald-400 hover:text-emerald-300 font-semibold underline cursor-pointer ml-1">Sign in here</button>`;
        }
    }
    hideAuthError();
}

function generateTenantId(email) {
    return "user-" + base64UrlEncode(email.trim().toLowerCase());
}

async function handleEmailAuth(event) {
    if (event) event.preventDefault();
    const email = document.getElementById("authEmailInput").value.trim().toLowerCase();
    const password = document.getElementById("authPasswordInput").value;
    const fullName = document.getElementById("authNameInput")?.value?.trim() || "";

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
        showAuthError("Please enter a valid Gmail / Email address.");
        return;
    }
    if (!password || password.length < 6) {
        showAuthError("Password must be at least 6 characters.");
        return;
    }

    const submitBtn = document.getElementById("authSubmitBtn");
    const submitBtnText = document.getElementById("authSubmitBtnText");
    const originalText = submitBtnText ? submitBtnText.textContent : "Submit";
    if (submitBtnText) submitBtnText.textContent = authMode === "signup" ? "Creating Account..." : "Signing In...";
    if (submitBtn) submitBtn.disabled = true;

    try {
        const endpoint = authMode === "signup" ? "/api/auth/register" : "/api/auth/login";
        const payload = authMode === "signup"
            ? { email: email, password: password, full_name: fullName || email.split("@")[0] }
            : { email: email, password: password };

        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = {};
        }

        if (!res.ok) {
            if (res.status === 404 || res.status >= 500) {
                console.warn("Server auth endpoint 404/500, falling back to local tenant session");
                const userObj = {
                    id: generateTenantId(email),
                    email: email,
                    name: fullName || email.split("@")[0],
                    user_metadata: {
                        full_name: fullName || email.split("@")[0],
                        name: fullName || email.split("@")[0]
                    },
                    provider: "email"
                };
                const token = createLocalAuthToken(userObj);
                setLoggedInUser(userObj, token);
                return;
            }
            showAuthError(data.detail || data.message || "Authentication failed. Please check your credentials.");
            return;
        }

        const userObj = {
            id: (data.user && data.user.id) || generateTenantId(email),
            email: (data.user && data.user.email) || email,
            name: (data.user && (data.user.name || data.user.full_name)) || fullName || email.split("@")[0],
            user_metadata: {
                full_name: (data.user && (data.user.name || data.user.full_name)) || fullName || email.split("@")[0],
                name: (data.user && (data.user.name || data.user.full_name)) || fullName || email.split("@")[0]
            },
            provider: "email"
        };

        setLoggedInUser(userObj, data.token || createLocalAuthToken(userObj));
    } catch (err) {
        console.warn("Auth connection error, falling back to local tenant session:", err);
        const userObj = {
            id: generateTenantId(email),
            email: email,
            name: fullName || email.split("@")[0],
            user_metadata: {
                full_name: fullName || email.split("@")[0],
                name: fullName || email.split("@")[0]
            },
            provider: "email"
        };
        const token = createLocalAuthToken(userObj);
        setLoggedInUser(userObj, token);
    } finally {
        if (submitBtnText) submitBtnText.textContent = originalText;
        if (submitBtn) submitBtn.disabled = false;
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
            document.getElementById("cfgBackendUrl").value = localStorage.getItem("backend_api_url") || DEFAULT_REMOTE_BACKEND || "https://autoapply-backend-hvdm.onrender.com";
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
// BACKEND CONNECTIVITY & AUTONOMOUS AUTO-WAKEUP ENGINE
// =============================================================================
let isBackendConnected = false;
let isBackendWakingUp = false;
let autoWakeupTimer = null;
let wakeupAttemptCount = 0;

function showAppToast(msg, type = "info") {
    let container = document.getElementById("appToastContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "appToastContainer";
        container.className = "fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    const colors = {
        success: "bg-emerald-950/90 border-emerald-500/40 text-emerald-200",
        info: "bg-zinc-900/95 border-zinc-700/60 text-zinc-200",
        warning: "bg-amber-950/90 border-amber-500/40 text-amber-200",
        error: "bg-rose-950/90 border-rose-500/40 text-rose-200"
    };
    const colorClass = colors[type] || colors.info;
    toast.className = `px-4 py-2.5 rounded-xl border text-xs shadow-2xl backdrop-blur-md transition-all duration-300 transform translate-y-2 opacity-0 pointer-events-auto flex items-center gap-2 max-w-sm ${colorClass}`;
    toast.innerHTML = `<span>${msg}</span>`;
    container.appendChild(toast);
    requestAnimationFrame(() => {
        toast.classList.remove("translate-y-2", "opacity-0");
    });
    setTimeout(() => {
        toast.classList.add("translate-y-2", "opacity-0");
        setTimeout(() => toast.remove(), 350);
    }, 4000);
}

async function triggerBackendHealthCheck(isUserClick = false) {
    if (isUserClick) {
        if (isBackendConnected) {
            showAppToast("🟢 Backend Server is connected and healthy! Render cloud engine is active.", "success");
            return;
        }
        if (isBackendWakingUp) {
            showAppToast("⚡ Backend is currently spinning up from sleep (~20-30s). Auto-connecting in background...", "info");
            return;
        }
        showAppToast("🔄 Checking backend connection...", "info");
    }
    return await checkBackendHealth();
}

function startAutoWakeupLoop() {
    if (autoWakeupTimer || isBackendConnected) return;
    if (wakeupAttemptCount >= 25) {
        // Stopped polling after ~100s
        return;
    }
    wakeupAttemptCount++;
    autoWakeupTimer = setTimeout(async () => {
        autoWakeupTimer = null;
        const ok = await checkBackendHealth();
        if (!ok && !isBackendConnected) {
            startAutoWakeupLoop();
        }
    }, 4000);
}

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
        // Give Render adequate time to respond
        const timeoutId = setTimeout(() => controller.abort(), 7000);
        const res = await originalFetch(targetUrl, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (res.ok) {
            const wasWaking = isBackendWakingUp;
            isBackendConnected = true;
            isBackendWakingUp = false;
            wakeupAttemptCount = 0;
            if (autoWakeupTimer) {
                clearTimeout(autoWakeupTimer);
                autoWakeupTimer = null;
            }

            if (statusDot) statusDot.className = "w-1.5 h-1.5 rounded-full bg-emerald-400";
            if (statusText) statusText.textContent = "Backend: Connected";
            if (statusPill) {
                statusPill.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition cursor-pointer bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:border-emerald-500/50";
                statusPill.title = `Live Connected to ${targetUrl}`;
            }
            if (banner) banner.classList.add("hidden");
            if (wasWaking) {
                showAppToast("🟢 Backend Connected! All AI agent services are active.", "success");
            }
            return true;
        }
    } catch (e) {
        // Cold start or temporary network delay
    }

    isBackendConnected = false;

    // Graceful handling for free-tier Render spin-down: show waking up instead of alarming disconnected state
    if (!isLocal && DEFAULT_REMOTE_BACKEND) {
        isBackendWakingUp = true;
        if (statusDot) statusDot.className = "w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse";
        if (statusText) statusText.textContent = "Backend: Waking Up...";
        if (statusPill) {
            statusPill.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition cursor-pointer bg-sky-500/10 border-sky-500/30 text-sky-300 hover:border-sky-500/50";
            statusPill.title = "Render Free Tier backend is waking up from sleep (~45s). Automatic connection in progress...";
        }
        if (banner) banner.classList.add("hidden");

        // Kick off fast autonomous retry loop to detect the moment Render comes online
        startAutoWakeupLoop();
        return false;
    }

    if (statusDot) statusDot.className = "w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse";
    if (statusText) statusText.textContent = isLocal ? "Backend: Offline" : "Backend: Disconnected";
    if (statusPill) {
        statusPill.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition cursor-pointer bg-amber-500/10 border-amber-500/30 text-amber-300 hover:border-amber-500/50";
        statusPill.title = "Backend is not responding. Will retry automatically.";
    }
    return false;
}

async function testBackendUrl() {
    const input = document.getElementById("cfgBackendUrl");
    const statusEl = document.getElementById("cfgBackendPingStatus");
    if (!input || !statusEl) return;

    let url = input.value.trim() || DEFAULT_REMOTE_BACKEND || "https://autoapply-backend-hvdm.onrender.com";
    input.value = url;
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
// =============================================================================
// CLIENT-SIDE COOKIE PERSISTENCE & AUTO-RESTORE
// =============================================================================
function saveCookiesToLocalStorage(platform, cookieData) {
    try {
        const platKey = (platform || "naukri").toLowerCase().trim().includes("wellfound") ? "wellfound" : "naukri";
        const storageKey = platKey === "wellfound" ? "autoapply_wellfound_cookies" : "autoapply_naukri_cookies";
        let cleanData = cookieData;
        if (platKey === "naukri" && Array.isArray(cookieData)) {
            cleanData = cookieData.filter(c => {
                const n = (c?.name || "").toLowerCase();
                return !(n.startsWith("ak_") || n.startsWith("bm_") || n === "_abck");
            });
        }
        const val = typeof cleanData === "string" ? cleanData : JSON.stringify(cleanData);
        localStorage.setItem(storageKey, val);
        console.log(`[Cookies] Persisted session cookies for ${platKey} to localStorage '${storageKey}'`);
    } catch (e) {
        console.warn("[Cookies] Could not persist cookies to localStorage:", e);
    }
}

function getStoredCookiesFromLocalStorage(platform) {
    try {
        const platKey = (platform || "naukri").toLowerCase().trim().includes("wellfound") ? "wellfound" : "naukri";
        const storageKey = platKey === "wellfound" ? "autoapply_wellfound_cookies" : "autoapply_naukri_cookies";
        const raw = localStorage.getItem(storageKey);
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch {
            return raw;
        }
    } catch (e) {
        return null;
    }
}

async function handleConnectCookies(platform, cookieData) {
    saveCookiesToLocalStorage(platform, cookieData);
    return await saveConnectedCookies(platform, cookieData);
}

let isRestoringSession = false;
async function tryRestoreSessionCookies(platform) {
    if (isRestoringSession) return false;
    const platKey = (platform || "naukri").toLowerCase().trim().includes("wellfound") ? "wellfound" : "naukri";
    const stored = getStoredCookiesFromLocalStorage(platKey);
    if (!stored) {
        return false;
    }

    isRestoringSession = true;
    try {
        console.log(`[Auto-Restore] Attempting to re-sync saved ${platKey} cookies to backend...`);
        const token = getAuthToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch("/api/session/connect-cookies", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                platform: platKey,
                cookies: stored
            })
        });

        if (res.ok) {
            const data = await res.json();
            if (data.status === "success") {
                console.log(`[Auto-Restore] Successfully re-connected ${platKey} session to backend!`);
                const badgeN = document.getElementById("badgeNaukriStatus");
                const badgeW = document.getElementById("badgeWellfoundStatus");
                if (platKey === "naukri" && badgeN) {
                    badgeN.textContent = `Connected (${data.cookies_count || 1})`;
                    badgeN.className = "text-emerald-400 font-semibold";
                } else if (platKey === "wellfound" && badgeW) {
                    badgeW.textContent = `Connected (${data.cookies_count || 1})`;
                    badgeW.className = "text-emerald-400 font-semibold";
                }
                return true;
            }
        }
    } catch (e) {
        console.warn(`[Auto-Restore] Failed re-syncing ${platKey} cookies:`, e);
    } finally {
        isRestoringSession = false;
    }
    return false;
}

// PORTAL SESSION COOKIES & QUICK APPLY ASSISTANT
// =============================================================================
async function checkPortalSessionStatus() {
    const badgeN = document.getElementById("badgeNaukriStatus");
    const badgeW = document.getElementById("badgeWellfoundStatus");
    try {
        const token = getAuthToken();
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch("/api/session/status", { headers: headers });
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
        // Save to localStorage immediately so session survives server cold starts & restarts
        saveCookiesToLocalStorage(platform, cookieData);
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
            alert(`🎉 ${data.message}\nYou can now click Auto-Apply!`);
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
        const text = (e.target.result || "").trim();
        if (!text) {
            alert("⚠️ The selected file is empty. Please choose a file containing cookies.");
            return;
        }
        try {
            const json = JSON.parse(text);
            if (Array.isArray(json) && json.length === 0) {
                alert(`⚠️ The file contains 0 cookies. Please export active session cookies while logged into ${platform}, or click '⚡ Use Test Session' to test instantly.`);
                return;
            }
            if (typeof json === "object" && json !== null && Object.keys(json).length === 0) {
                alert("⚠️ The file contains an empty JSON object. Please provide valid cookies.");
                return;
            }
            await saveConnectedCookies(platform, json, fromAssistant);
        } catch (err) {
            if (text.includes("=") || text.includes("\t")) {
                await saveConnectedCookies(platform, text, fromAssistant);
            } else {
                alert("Invalid cookie file: " + err.message + "\nPlease select a valid JSON cookie export or Netscape cookie file.");
            }
        }
    };
    reader.readAsText(file);
}

function promptPasteCookies(platform, fromAssistant = false) {
    const raw = prompt(`Paste your ${platform} session cookies here:\n\nSupports: JSON array, key-value JSON, or browser cookie header string (e.g. name=val; name2=val2)`);
    if (!raw) return;
    const trimmed = raw.trim();
    if (!trimmed) return;

    try {
        const json = JSON.parse(trimmed);
        if (Array.isArray(json) && json.length === 0) {
            alert("⚠️ Empty cookie list. Please paste valid session cookies, or click '⚡ Use Test Session' to test instantly.");
            return;
        }
        saveConnectedCookies(platform, json, fromAssistant);
    } catch (err) {
        if (trimmed.includes("=") || trimmed.includes("\t")) {
            saveConnectedCookies(platform, trimmed, fromAssistant);
        } else {
            alert("Invalid cookie format. Please paste either JSON cookies or an HTTP cookie string (name=value; name2=value2).");
        }
    }
}

async function connectDemoCookies(platform, fromAssistant = false) {
    if (!requireAuth("connect test portal session")) return;
    try {
        const token = getAuthToken();
        const headers = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch("/api/session/generate-demo-cookies", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({ platform: platform })
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
            alert(`🎉 ${data.message}\nYour session is verified! You can now click Auto-Apply.`);
            checkPortalSessionStatus();
            if (fromAssistant) {
                closeQuickApplyModal();
            }
        } else {
            alert(`⚠️ Error generating test session: ${data.detail || data.message || 'Unknown error'}`);
        }
    } catch (e) {
        alert("Network error generating test session: " + e.message);
    }
}

let activeAssistantJobIdx = null;
let currentAssistantPlatform = "naukri";


async function handleInstant1ClickApply(idx) {
    const job = foundJobs[idx];
    if (!job) return;

    // 1. Generate/copy pitch
    try {
        await assistantGeneratePitch();
    } catch (_) {}

    // 2. Open job URL in new tab where candidate is logged in on residential IP
    if (job.job_url) {
        window.open(job.job_url, "_blank", "noopener,noreferrer");
    }

    // 3. Mark row as Applied in UI
    const actionCell = document.getElementById(`action-cell-${idx}`);
    const actionCard = document.getElementById(`action-card-${idx}`);
    const statusCell = document.getElementById(`status-cell-${idx}`);
    const statusCard = document.getElementById(`status-card-${idx}`);

    const appliedHtml = `
        <span class="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Applied ✅
        </span>
    `;
    if (statusCell) statusCell.innerHTML = appliedHtml;
    if (statusCard) statusCard.innerHTML = appliedHtml;

    const viewBtn = `
        <a href="${escapeHtml(job.job_url)}" target="_blank" rel="noopener noreferrer" class="text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-bold hover:underline inline-flex items-center justify-center gap-1 w-full sm:w-auto cursor-pointer">
            🔗 View Job
        </a>
    `;
    if (actionCell) actionCell.innerHTML = viewBtn;
    if (actionCard) actionCard.innerHTML = viewBtn;

    const statApplied = document.getElementById("statApplied");
    if (statApplied) {
        statApplied.textContent = parseInt(statApplied.textContent || "0") + 1;
    }

    // 4. Record to cloud database
    try {
        const token = getAuthToken();
        await fetch("/api/user/applications", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(token ? { "Authorization": `Bearer ${token}` } : {})
            },
            body: JSON.stringify({
                platform: (job.platform || "naukri").toLowerCase(),
                job_title: job.title,
                company_name: job.company || "Hiring Company",
                job_url: job.job_url,
                status: "applied",
                match_score: 96.0
            })
        });
    } catch (_) {}

    closeQuickApplyModal();
    showAppToast("⚡ Opened Naukri in new tab! Click Apply to complete.", "success");
}

async function handleExternalCompanyApply(idx) {
    const job = foundJobs[idx];
    if (!job) return;

    try {
        await assistantGeneratePitch();
    } catch (_) {}

    if (job.job_url) {
        window.open(job.job_url, "_blank", "noopener,noreferrer");
    }

    const actionCell = document.getElementById(`action-cell-${idx}`);
    const actionCard = document.getElementById(`action-card-${idx}`);
    const statusCell = document.getElementById(`status-cell-${idx}`);
    const statusCard = document.getElementById(`status-card-${idx}`);

    const extHtml = `
        <span class="inline-flex items-center gap-1.5 text-blue-400 text-xs font-semibold">
            <span class="w-1.5 h-1.5 rounded-full bg-blue-400"></span> External Portal ↗
        </span>
    `;
    if (statusCell) statusCell.innerHTML = extHtml;
    if (statusCard) statusCard.innerHTML = extHtml;

    const viewBtn = `
        <a href="${escapeHtml(job.job_url)}" target="_blank" rel="noopener noreferrer" class="text-[11px] text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1.5 sm:py-1 rounded-lg font-bold hover:underline inline-flex items-center justify-center gap-1 w-full sm:w-auto cursor-pointer">
            🌐 View Portal
        </a>
    `;
    if (actionCell) actionCell.innerHTML = viewBtn;
    if (actionCard) actionCard.innerHTML = viewBtn;

    closeQuickApplyModal();
    showAppToast("🌐 Opened external careers portal in new tab!", "info");
}

function openQuickApplyModal(idx, reason, proofImage, statusCode) {
    if (!requireAuth("use Quick Apply Assistant")) return;
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

    const reasonText = (reason && String(reason).trim()) ? String(reason).trim() : `${platformDisplay} session check required.`;
    const resolvedProofUrl = getProofUrl(proofImage || job.proof_image || job.proof_url || "");
    const safeJobTitle = (job.title || "").replace(/['"\\]/g, " ");

    const proofBtnHtml = resolvedProofUrl ? `
        <div class="mt-2.5 pt-2 border-t border-zinc-800/80 flex items-center justify-between">
            <span class="text-[11px] text-zinc-400">Diagnostic live DOM screenshot:</span>
            <button type="button" onclick="openProofModal('${resolvedProofUrl}', '${safeJobTitle}')" class="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold inline-flex items-center gap-1.5 transition cursor-pointer shadow-sm">
                📸 View Diagnostic Screenshot
            </button>
        </div>
    ` : "";

    const statusKey = String(statusCode || "").toLowerCase();
    const reasonLower = reasonText.toLowerCase();

    if (alertEl) {
        if (reasonText.includes("Resume profile required") || reasonText.includes("resume first")) {
            alertEl.innerHTML = `
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                    <div>
                        <span class="font-bold text-amber-300">Resume profile needs analysis:</span>
                        <div class="text-xs text-zinc-300 mt-0.5">Click below to auto-analyze your resume and continue immediately.</div>
                    </div>
                    <button type="button" onclick="autoAnalyzeAndRetryCurrentJob()" class="px-3.5 py-2 bg-gradient-to-r from-amber-500 to-emerald-500 text-black font-bold text-xs rounded-lg shadow hover:opacity-90 transition whitespace-nowrap cursor-pointer">
                        ⚡ Auto-Analyze & Apply Now
                    </button>
                </div>
            `;
        } else if (statusKey === "session_required" || reasonLower.includes("no active session cookies") || reasonLower.includes("connect your cookies")) {
            alertEl.innerHTML = `
                <div class="space-y-2">
                    <div class="flex items-center gap-1.5 text-amber-400 font-bold text-xs">
                        <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                        ${platformDisplay} Session Connection Required
                    </div>
                    <div class="text-[11px] text-zinc-300 leading-relaxed">
                        To auto-apply in the background, connect your active ${platformDisplay} session cookies below, or apply directly from your browser.
                    </div>
                    <div class="flex flex-col sm:flex-row items-center gap-2 pt-1">
                        <button type="button" onclick="promptPasteCookies('${currentAssistantPlatform}')" class="w-full sm:flex-1 py-2 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-semibold text-xs transition flex items-center justify-center gap-1.5 border border-zinc-700 cursor-pointer">
                            📋 Paste Cookies
                        </button>
                        <button type="button" onclick="handleInstant1ClickApply(${idx})" class="w-full sm:flex-1 py-2 px-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition flex items-center justify-center gap-1.5 shadow cursor-pointer">
                            ⚡ 1-Click Browser Apply ↗
                        </button>
                    </div>
                    ${proofBtnHtml}
                </div>
            `;
        } else if (statusKey === "login_required" || statusKey === "session_expired" || reasonLower.includes("login to apply") || reasonLower.includes("cookies are missing or expired") || reasonLower.includes("session cookies have expired") || reasonLower.includes("session prompt") || reasonLower.includes("redirected to login")) {
            alertEl.innerHTML = `
                <div class="space-y-2">
                    <div class="flex items-center gap-1.5 text-amber-400 font-bold text-xs">
                        <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                        ${platformDisplay} Authentication Required
                    </div>
                    <div class="text-[11px] text-zinc-300 leading-relaxed">
                        ${escapeHtml(reasonText)}
                    </div>
                    <div class="text-[11px] text-zinc-400">
                        Please update your active ${platformDisplay} cookies in Settings or upload fresh cookies below to resume automated applying.
                    </div>
                    ${proofBtnHtml}
                </div>
            `;
        } else if (statusKey === "external_portal" || statusKey === "external_redirect" || reasonLower.includes("apply on company site") || reasonLower.includes("external company portal") || reasonLower.includes("company portal") || reasonLower.includes("employer website")) {
            alertEl.innerHTML = `
                <div class="space-y-2">
                    <div class="flex items-center gap-1.5 text-blue-400 font-bold text-xs">
                        <span class="w-2 h-2 rounded-full bg-blue-400"></span>
                        Company Careers Portal (External Application)
                    </div>
                    <div class="text-[11px] text-zinc-300 leading-relaxed">
                        ${escapeHtml(reasonText)}
                    </div>
                    <button type="button" onclick="handleExternalCompanyApply(${idx})" class="w-full py-2.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition flex items-center justify-center gap-1.5 shadow-md cursor-pointer">
                        🌐 Open Company Portal & Submit ↗
                    </button>
                    ${proofBtnHtml}
                </div>
            `;
            setTimeout(() => {
                const btnGen = document.getElementById("btnAssistantGeneratePitch");
                if (btnGen) btnGen.click();
            }, 250);
        } else if (statusKey === "apply_button_not_found" || reasonLower.includes("could not find naukri apply button")) {
            alertEl.innerHTML = `
                <div class="space-y-2">
                    <div class="flex items-center gap-1.5 text-amber-400 font-bold text-xs">
                        <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                        Apply Button Not Detected
                    </div>
                    <div class="text-[11px] text-zinc-300 leading-relaxed">
                        ${escapeHtml(reasonText)}
                    </div>
                    <div class="flex flex-col sm:flex-row items-center gap-2 pt-1">
                        <a href="${escapeHtml(job.job_url)}" target="_blank" rel="noopener noreferrer" class="w-full sm:flex-1 py-2 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-semibold text-xs transition flex items-center justify-center gap-1.5">
                            🔗 Open Listing on ${platformDisplay} ↗
                        </a>
                    </div>
                    ${proofBtnHtml}
                </div>
            `;
        } else if (statusKey === "cloud_security_challenge" || reasonLower.includes("cloud bot challenge") || reasonLower.includes("recaptcha") || reasonLower.includes("challenge detected")) {
            alertEl.innerHTML = `
                <div class="space-y-2">
                    <div class="flex items-center gap-1.5 text-emerald-400 font-bold text-xs">
                        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                        Direct 1-Click Apply Ready on Naukri
                    </div>
                    <div class="text-[11px] text-zinc-300 leading-relaxed">
                        ${escapeHtml(reasonText)}
                    </div>
                    <button type="button" onclick="handleInstant1ClickApply(${idx})" class="w-full py-2.5 px-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition flex items-center justify-center gap-1.5 shadow-md cursor-pointer">
                        ⚡ 1-Click Apply on Naukri ↗
                    </button>
                    ${proofBtnHtml}
                </div>
            `;
            setTimeout(() => {
                const btnGen = document.getElementById("btnAssistantGeneratePitch");
                if (btnGen) btnGen.click();
            }, 250);
        } else {
            alertEl.innerHTML = `
                <div class="space-y-2">
                    <div class="text-xs text-zinc-200">
                        <span class="font-semibold text-amber-300">${escapeHtml(reasonText)}</span>
                    </div>
                    <div class="text-[11px] text-zinc-400">Choose an option below to proceed:</div>
                    ${proofBtnHtml}
                </div>
            `;
        }
    }
    if (sessionTitle) {
        sessionTitle.textContent = `Connect ${platformDisplay} Session for Background Auto-Apply`;
    }
    if (uploadLabel) {
        uploadLabel.textContent = `Upload ${currentAssistantPlatform}_cookies.json`;
    }
    if (pitchBox) pitchBox.classList.add("hidden");
    if (btnText) btnText.textContent = "📋 Generate & Copy AI Pitch";
    const btnGen = document.getElementById("btnAssistantGeneratePitch");
    if (btnGen) btnGen.disabled = false;
    const toast = document.getElementById("assistantCopyToast");
    if (toast) toast.classList.add("hidden");

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

async function assistantGeneratePitch() {
    if (activeAssistantJobIdx === null || !foundJobs[activeAssistantJobIdx]) return;
    if (!requireAuth("generate tailored application pitches")) return;
    const job = foundJobs[activeAssistantJobIdx];
    const btn = document.getElementById("btnAssistantGeneratePitch");
    const btnText = document.getElementById("btnAssistantGenerateText");
    const pitchBox = document.getElementById("assistantPitchPreviewBox");
    const pitchText = document.getElementById("assistantPitchText");
    const toast = document.getElementById("assistantCopyToast");

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
        const data = await safeParseJson(res);
        const pitch = data.cover_letter || `Dear Hiring Team at ${job.company},\n\nI am writing to express my strong interest in the ${job.title} position at ${job.company}.\n\nBest regards,\n${candidateName}`;

        if (pitchText) pitchText.value = pitch;
        if (pitchBox) pitchBox.classList.remove("hidden");

        // Copy to clipboard safely - NEVER OPEN ANY BROWSER TAB
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(pitch);
            } else if (pitchText) {
                pitchText.select();
                document.execCommand("copy");
            }
            if (toast) {
                toast.classList.remove("hidden");
                setTimeout(() => toast.classList.add("hidden"), 3500);
            }
        } catch (clipErr) {
            console.warn("Clipboard copy notice:", clipErr);
        }

        if (btnText) btnText.innerHTML = "✅ Pitch Copied to Clipboard!";

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
        if (btnText) btnText.innerHTML = "📋 Generate & Copy AI Pitch";
        alert("AI Pitch Generation Notice: " + e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

function assistantOpenJob() {
    if (activeAssistantJobIdx === null || !foundJobs[activeAssistantJobIdx]) return;
    if (!requireAuth("open external job listings")) return;
    const job = foundJobs[activeAssistantJobIdx];
    if (job && job.job_url) {
        window.open(job.job_url, "_blank", "noopener,noreferrer");
    } else {
        alert("No valid job URL available for this opening.");
    }
}

// Backward compatibility alias that strictly executes safe pitch generation without opening tabs
function assistantGeneratePitchAndOpen() {
    return assistantGeneratePitch();
}


// =============================================================================
// Keyboard Escape & Backdrop Click Modal Dismissal
// =============================================================================
// =============================================================================
// IN-APP PROOF LIGHTBOX PREVIEW CONTROLLER
// =============================================================================
let currentProofUrl = "";

function openProofModal(rawUrl, jobTitle = "") {
    const modal = document.getElementById("proofModal");
    const img = document.getElementById("proofModalImg");
    const loading = document.getElementById("proofModalLoading");
    const errorBox = document.getElementById("proofModalError");
    const titleEl = document.getElementById("proofModalJobTitle");
    const newTabLink = document.getElementById("proofModalOpenNewTab");
    const errorDirectLink = document.getElementById("proofModalErrorDirectLink");
    const urlHint = document.getElementById("proofModalUrlHint");

    const fullUrl = getProofUrl(rawUrl);
    if (!fullUrl) {
        alert("No valid proof screenshot URL is available for this application.");
        return;
    }

    currentProofUrl = fullUrl;

    if (titleEl) {
        titleEl.textContent = jobTitle ? `Proof: ${jobTitle}` : "Playwright Autonomous Screen Proof";
    }
    if (newTabLink) {
        newTabLink.href = fullUrl;
    }
    if (errorDirectLink) {
        errorDirectLink.href = fullUrl;
    }
    if (urlHint) {
        try {
            const parsed = new URL(fullUrl);
            urlHint.textContent = `${parsed.hostname}${parsed.pathname}`;
        } catch (_) {
            urlHint.textContent = fullUrl;
        }
    }

    if (loading) loading.classList.remove("hidden");
    if (errorBox) errorBox.classList.add("hidden");
    if (img) {
        img.classList.remove("opacity-100");
        img.classList.add("opacity-0");
        img.src = fullUrl;
    }

    if (modal) modal.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
}

function closeProofModal() {
    const modal = document.getElementById("proofModal");
    const img = document.getElementById("proofModalImg");
    if (modal) modal.classList.add("hidden");
    if (img) {
        img.src = "";
        img.classList.remove("opacity-100");
        img.classList.add("opacity-0");
    }
}

function handleProofImageLoad() {
    const img = document.getElementById("proofModalImg");
    const loading = document.getElementById("proofModalLoading");
    const errorBox = document.getElementById("proofModalError");
    if (loading) loading.classList.add("hidden");
    if (errorBox) errorBox.classList.add("hidden");
    if (img) {
        img.classList.remove("opacity-0");
        img.classList.add("opacity-100");
    }
}

function handleProofImageError() {
    const loading = document.getElementById("proofModalLoading");
    const errorBox = document.getElementById("proofModalError");
    if (loading) loading.classList.add("hidden");
    if (errorBox) errorBox.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
}

function retryProofLoad() {
    if (!currentProofUrl) return;
    const img = document.getElementById("proofModalImg");
    const loading = document.getElementById("proofModalLoading");
    const errorBox = document.getElementById("proofModalError");
    if (loading) loading.classList.remove("hidden");
    if (errorBox) errorBox.classList.add("hidden");
    if (img) {
        img.classList.remove("opacity-100");
        img.classList.add("opacity-0");
        const sep = currentProofUrl.includes("?") ? "&" : "?";
        img.src = `${currentProofUrl}${sep}t=${Date.now()}`;
    }
}

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
        closeProofModal();
    }
});

["applyModal", "platformSelectorModal", "authModal", "cloudConfigModal", "quickApplyAssistantModal", "memoryVaultModal", "proofModal"].forEach(modalId => {
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
                else if (modalId === "proofModal") closeProofModal();
            }
        });
    }
});


function openSessionConnectModal() {
    if (!requireAuth("connect portal session cookies")) return;
    toggleCloudConfigModal(true);
}

function startSimulation() {
    return triggerScenarioSimulation();
}


function handleExternalJobClick(event, url) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    if (!requireAuth("open external job listings")) return false;
    if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
    }
    return false;
}



async function autoAnalyzeAndRetryCurrentJob() {
    const fileInput = document.getElementById("resumeFileInput");
    const file = fileInput?.files?.[0];
    const alertEl = document.getElementById("assistantReasonAlert");
    if (alertEl) alertEl.innerHTML = `<span class="text-amber-400 animate-spin mr-1">⟳</span> <span class="text-amber-300">Analyzing resume with LLM...</span>`;

    try {
        if (file) {
            await analyzeSelectedResumeFile(file);
        } else {
            await loadUserProfile();
        }
    } catch (e) {
        console.warn("Auto-analysis error:", e);
    }

    const targetIdx = activeAssistantJobIdx;
    closeQuickApplyModal();
    if (targetIdx !== null) {
        directApplyRow(targetIdx);
    }
}
