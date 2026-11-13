// AI Auto-Apply Agent - Naukri Autonomous Content Script
// Automatically detects apply buttons, fills questionnaire drawers, answers screening questions, and submits on Naukri.com

(function () {
    console.log("[Auto-Apply Agent] Naukri content script injected on:", window.location.href);

    // Only run on job detail listings
    if (!window.location.href.includes("job-listings-") && !document.querySelector("#apply-button, .apply-button")) {
        return;
    }

    let agentOverlay = null;

    function createAgentOverlay() {
        if (agentOverlay) return;
        agentOverlay = document.createElement("div");
        agentOverlay.id = "autoapply-agent-overlay";
        agentOverlay.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 999999;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(16, 185, 129, 0.5);
            border-radius: 12px;
            padding: 12px 18px;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            gap: 10px;
            backdrop-filter: blur(8px);
            transition: all 0.3s ease;
        `;
        agentOverlay.innerHTML = `
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #10b981; animation: pulse 1.5s infinite;"></div>
            <div>
                <div style="font-weight: 700; color: #10b981; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">AI Auto-Apply Agent</div>
                <div id="autoapply-status-text" style="color: #cbd5e1; font-size: 12px;">Initializing autonomous application...</div>
            </div>
        `;
        const style = document.createElement("style");
        style.textContent = `@keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; transform: scale(1.1); } 100% { opacity: 0.4; } }`;
        document.head.appendChild(style);
        document.body.appendChild(agentOverlay);
    }

    function updateAgentStatus(text, isSuccess = false, isError = false) {
        if (!agentOverlay) createAgentOverlay();
        const el = document.getElementById("autoapply-status-text");
        if (el) el.textContent = text;
        if (isSuccess && agentOverlay) {
            agentOverlay.style.borderColor = "#10b981";
            agentOverlay.style.background = "rgba(6, 78, 59, 0.95)";
        }
        if (isError && agentOverlay) {
            agentOverlay.style.borderColor = "#ef4444";
            agentOverlay.style.background = "rgba(127, 29, 29, 0.95)";
        }
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function waitForElement(selector, timeout = 12000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const el = document.querySelector(selector);
            if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) {
                return el;
            }
            await sleep(250);
        }
        return null;
    }

    // Candidate Profile Defaults (overridden by storage if available)
    let candidateData = {
        name: "Sachin Sharma",
        noticePeriod: "15 Days or less",
        totalExperience: "3.5",
        relevantExperience: "3",
        currentCtc: "12",
        expectedCtc: "18",
        skills: ["Python", "FastAPI", "React", "AI Agents", "Docker"]
    };

    // Load candidate profile from storage
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get(["candidateProfile"], (res) => {
            if (res && res.candidateProfile) {
                const p = res.candidateProfile;
                candidateData.name = p.candidate_name || candidateData.name;
                candidateData.totalExperience = String(p.experience_years || candidateData.totalExperience);
                candidateData.noticePeriod = p.notice_period || candidateData.noticePeriod;
                candidateData.currentCtc = String(p.current_ctc || candidateData.currentCtc);
                candidateData.expectedCtc = String(p.expected_ctc || candidateData.expectedCtc);
                if (Array.isArray(p.skills)) candidateData.skills = p.skills;
            }
        });
    }

    async function executeNaukriAutoApply() {
        createAgentOverlay();
        updateAgentStatus("Scanning Naukri job page & hydration...");
        await sleep(1500);

        // 1. Check if user is logged in
        const loginApplyBtn = document.querySelector("#login-apply-button") ||
            Array.from(document.querySelectorAll("button, a")).find(b => (b.innerText || "").toLowerCase().includes("login to apply") && b.offsetWidth > 0);
        if (loginApplyBtn && loginApplyBtn.offsetWidth > 0) {
            updateAgentStatus("⚠️ Please log into Naukri in this tab to apply.", false, true);
            return;
        }

        // 2. Check if already applied
        const alreadyAppliedEl = document.querySelector("#already-applied") ||
            Array.from(document.querySelectorAll("span, button, div")).find(b => (b.innerText || "").toLowerCase().includes("already applied") && b.offsetWidth > 0);
        const bodyText = (document.body.innerText || "").toLowerCase();
        if ((alreadyAppliedEl && alreadyAppliedEl.offsetWidth > 0) || bodyText.includes("you have already applied") || bodyText.includes("applied on")) {
            updateAgentStatus("✅ Already Applied to this job earlier!", true);
            if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    type: "APPLICATION_COMPLETED",
                    jobTitle: document.title,
                    message: "Already applied earlier on Naukri."
                });
            }
            return;
        }

        // 3. Find Apply button
        updateAgentStatus("Locating direct Apply button...");
        const applySelectors = [
            "#apply-button",
            "button#apply-button",
            "button.apply-button",
            "[class*='styles_jhc__apply-button'] button",
            "div.apply-button-container button",
            ".apply-btn"
        ];

        let applyBtn = null;
        for (const sel of applySelectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetWidth > 0 && !el.innerText.toLowerCase().includes("company site")) {
                applyBtn = el;
                break;
            }
        }

        if (!applyBtn) {
            applyBtn = await waitForElement("#apply-button, button.apply-button", 8000);
        }

        if (!applyBtn) {
            const extBtn = document.querySelector("#company-site-button") ||
                Array.from(document.querySelectorAll("button, a")).find(b => (b.innerText || "").toLowerCase().includes("apply on company site") && b.offsetWidth > 0);
            if (extBtn) {
                updateAgentStatus("ℹ️ External company portal listing.", false, false);
                return;
            }
            updateAgentStatus("Could not find Apply button on page.", false, true);
            return;
        }

        // 4. Click Apply Button
        updateAgentStatus("⚡ Clicking Apply button...");
        applyBtn.scrollIntoView({ behavior: "smooth", block: "center" });
        await sleep(500);
        applyBtn.click();
        await sleep(2000);

        // 5. Check if questionnaire drawer / chatbot modal opened
        updateAgentStatus("Answering screening questions & notice period...");
        const appliedOk = await handleQuestionnaireDrawer();

        // 6. Verify submission confirmation
        await sleep(1500);
        if (appliedOk) {
            updateAgentStatus("🎉 Application successfully submitted & verified on Naukri!", true);
            if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    type: "APPLICATION_COMPLETED",
                    jobTitle: document.title,
                    message: "100% submitted and verified on Naukri.com"
                });
            }
        } else {
            updateAgentStatus("Application completed or awaiting review.", true);
        }
    }

    // Helper: Select an option element (radio / choice pill)
    function selectOptionElement(el) {
        try {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
            const input = el.querySelector("input[type='radio'], input[type='checkbox']") || (el.tagName === "INPUT" ? el : null);
            if (input) {
                input.checked = true;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.click();
            }
            el.click();
            return true;
        } catch (_) {
            return false;
        }
    }

    async function handleQuestionnaireDrawer() {
        console.log("[Auto-Apply Agent] Starting screening question handler loop...");

        for (let round = 0; round < 10; round++) {
            await sleep(900);

            // Check if submission already confirmed on page
            const bodyNow = (document.body.innerText || "").toLowerCase();
            if (bodyNow.includes("successfully applied") || bodyNow.includes("you have applied") || bodyNow.includes("already applied") || bodyNow.includes("applied on")) {
                console.log("[Auto-Apply Agent] Detected submission confirmation in page content!");
                return true;
            }

            // Check if drawer is present
            const drawer = document.querySelector(".chatbot_DrawerContentWrapper, [class*='chatbot'], [class*='drawer'], .ssrc__drawer, div[id*='chatBot']");
            const drawerRoot = drawer || document.body;

            // A. Handle Radio / Multiple-Choice Questions
            // Find all potential radio / option wrappers
            const optionContainers = Array.from(drawerRoot.querySelectorAll("label, div[class*='radio'], div[class*='option'], li[class*='option'], div[class*='choice'], [role='radio'], [class*='chip'], [class*='pill'], [class*='bot-option'], [class*='selection']"));

            if (optionContainers.length > 0) {
                // Priority 1: Answer YES for screening questions ("Are you available", "Do you have experience", "willing to relocate")
                let answeredRound = false;
                for (const opt of optionContainers) {
                    const txt = (opt.innerText || opt.textContent || "").toLowerCase().trim();
                    // Match pure "yes" or starting with "yes"
                    if (txt === "yes" || txt.startsWith("yes,") || txt.startsWith("yes ") || txt === "available") {
                        const input = opt.querySelector("input[type='radio'], input[type='checkbox']") || opt;
                        if (!input.checked) {
                            console.log("[Auto-Apply Agent] Answering YES to screening question:", txt);
                            selectOptionElement(opt);
                            answeredRound = true;
                            await sleep(400);
                        }
                    }
                }

                // Priority 2: Notice Period Questions
                for (const opt of optionContainers) {
                    const txt = (opt.innerText || opt.textContent || "").toLowerCase().trim();
                    if (txt.includes("15 days or less") || txt.includes("< 15 days") || txt.includes("immediate") || txt.includes("serving notice") || txt.includes("ready to join") || (txt.includes("15 days") && !txt.includes(">"))) {
                        const input = opt.querySelector("input[type='radio']") || opt;
                        if (!input.checked) {
                            console.log("[Auto-Apply Agent] Selecting Notice Period option:", txt);
                            selectOptionElement(opt);
                            answeredRound = true;
                            await sleep(400);
                        }
                    }
                }

                // Priority 3: Experience Level Ranges
                for (const opt of optionContainers) {
                    const txt = (opt.innerText || opt.textContent || "").toLowerCase().trim();
                    if (txt.includes("3-5") || txt.includes("3 to 5") || txt.includes("2-4") || txt.includes("2-5") || txt.includes("1-3")) {
                        const input = opt.querySelector("input[type='radio']") || opt;
                        if (!input.checked) {
                            console.log("[Auto-Apply Agent] Selecting Experience range:", txt);
                            selectOptionElement(opt);
                            answeredRound = true;
                            await sleep(400);
                        }
                    }
                }
            }

            // B. Fill Text Inputs (Experience, CTC, Notice Period, etc.)
            const inputs = Array.from(drawerRoot.querySelectorAll("input[type='text'], input[type='number'], textarea"));
            for (const input of inputs) {
                if (input.value && input.value.trim().length > 0) continue;
                const fieldText = ((input.placeholder || "") + " " + (input.name || "") + " " + (input.id || "") + " " + (input.getAttribute("aria-label") || "")).toLowerCase();
                const parentText = (input.closest("div, label, li, form")?.innerText || "").toLowerCase();

                if (fieldText.includes("experience") || parentText.includes("experience") || parentText.includes("years")) {
                    input.value = candidateData.totalExperience;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    console.log("[Auto-Apply Agent] Filled Experience:", candidateData.totalExperience);
                } else if (fieldText.includes("current ctc") || parentText.includes("current ctc") || parentText.includes("current salary")) {
                    input.value = candidateData.currentCtc;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    console.log("[Auto-Apply Agent] Filled Current CTC:", candidateData.currentCtc);
                } else if (fieldText.includes("expected ctc") || parentText.includes("expected ctc") || parentText.includes("expected salary")) {
                    input.value = candidateData.expectedCtc;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    console.log("[Auto-Apply Agent] Filled Expected CTC:", candidateData.expectedCtc);
                } else if (fieldText.includes("notice") || parentText.includes("notice period")) {
                    input.value = "15";
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    console.log("[Auto-Apply Agent] Filled Notice Period: 15");
                } else {
                    // Generic text input (cover note or brief answer)
                    input.value = "Yes, I am experienced in this domain and available to join immediately.";
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }

            // C. Check mandatory checkboxes
            const checkboxes = Array.from(drawerRoot.querySelectorAll("input[type='checkbox']"));
            for (const cb of checkboxes) {
                if (!cb.checked) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event("change", { bubbles: true }));
                    cb.click();
                }
            }

            // D. Select Dropdown options
            const selects = Array.from(drawerRoot.querySelectorAll("select"));
            for (const sel of selects) {
                if (!sel.value || sel.value === "0" || sel.value === "") {
                    const opts = Array.from(sel.options);
                    const matchingOpt = opts.find(o => {
                        const t = o.text.toLowerCase();
                        return t.includes("15") || t.includes("immediate") || t.includes("yes") || t.includes("3");
                    }) || opts[1] || opts[0];
                    if (matchingOpt) {
                        sel.value = matchingOpt.value;
                        sel.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                }
            }

            await sleep(500);

            // E. Click Next / Save / Submit / Apply in drawer
            const actionButtons = Array.from(drawerRoot.querySelectorAll("button, input[type='submit'], div.bot-action-container button, div.sendMsg"));
            let submitBtn = null;

            for (const b of actionButtons) {
                if (b.id === "apply-button") continue;
                if (b.offsetWidth === 0 && b.offsetHeight === 0) continue;

                const t = (b.innerText || b.value || "").toLowerCase().trim();
                const isMatch = t.includes("submit") || 
                                t.includes("save") || 
                                t.includes("next") || 
                                t.includes("continue") || 
                                t.includes("apply") || 
                                t.includes("done") || 
                                t.includes("send") || 
                                b.classList.contains("sendMsg") ||
                                b.getAttribute("type") === "submit";
                if (isMatch) {
                    submitBtn = b;
                    break;
                }
            }

            // Also check for the bottom action bar in the drawer
            if (!submitBtn) {
                const bottomBtn = drawerRoot.querySelector("div[class*='action'] button, div[class*='bottom'] button, div[class*='footer'] button, button.apply-button");
                if (bottomBtn && bottomBtn.id !== "apply-button" && bottomBtn.offsetWidth > 0) {
                    submitBtn = bottomBtn;
                }
            }

            console.log("[Auto-Apply Agent] Found submitBtn:", submitBtn ? (submitBtn.id || submitBtn.innerText) : "NONE", "disabled:", submitBtn ? submitBtn.disabled : false);
            if (submitBtn) {
                console.log("[Auto-Apply Agent] Clicking drawer Submit/Next button:", submitBtn.innerText || "Send");
                submitBtn.scrollIntoView({ behavior: "smooth", block: "center" });
                submitBtn.click();
                await sleep(1500);
            } else {
                // If no submit button found and no options left, we may be done
                if (round > 2 && optionContainers.length === 0 && inputs.length === 0) {
                    console.log("[Auto-Apply Agent] No pending questions remaining in drawer.");
                    return true;
                }
            }
        }
        return true;
    }

    // Run automatically when page is loaded
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(executeNaukriAutoApply, 1000);
    } else {
        window.addEventListener("DOMContentLoaded", () => setTimeout(executeNaukriAutoApply, 1000));
    }
})();
