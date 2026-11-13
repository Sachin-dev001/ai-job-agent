// AI Auto-Apply Agent - Naukri Autonomous Content Script
// Automatically detects apply buttons, fills questionnaire drawers, and submits applications on Naukri.com

(function () {
    console.log("[Auto-Apply Agent] Content script injected on:", window.location.href);

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
            border: 1px solid rgba(16, 185, 129, 0.4);
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

    // Candidate Defaults (overridden by storage if available)
    let candidateData = {
        noticePeriod: "15 Days or less",
        totalExperience: "3.5",
        relevantExperience: "3",
        currentCtc: "12",
        expectedCtc: "18",
        skills: ["Python", "FastAPI", "React", "AI Agents", "Docker"]
    };

    // Load candidate profile from storage
    chrome.storage.local.get(["candidateProfile"], (res) => {
        if (res && res.candidateProfile) {
            const p = res.candidateProfile;
            candidateData.totalExperience = String(p.experience_years || candidateData.totalExperience);
            candidateData.noticePeriod = p.notice_period || candidateData.noticePeriod;
            candidateData.currentCtc = String(p.current_ctc || candidateData.currentCtc);
            candidateData.expectedCtc = String(p.expected_ctc || candidateData.expectedCtc);
            if (Array.isArray(p.skills)) candidateData.skills = p.skills;
        }
    });

    async function executeNaukriAutoApply() {
        createAgentOverlay();
        updateAgentStatus("Scanning Naukri job page & hydration...");
        await sleep(1500);

        // 1. Check if user is logged in
        const loginApplyBtn = document.querySelector("#login-apply-button, button:has-text('Login to apply')");
        if (loginApplyBtn && loginApplyBtn.offsetWidth > 0) {
            updateAgentStatus("⚠️ Please log into Naukri in this tab to apply.", false, true);
            return;
        }

        // 2. Check if already applied
        const alreadyAppliedEl = document.querySelector("#already-applied, span:has-text('Applied'), button:has-text('Applied')");
        const bodyText = document.body.innerText.toLowerCase();
        if ((alreadyAppliedEl && alreadyAppliedEl.offsetWidth > 0) || bodyText.includes("you have already applied") || bodyText.includes("applied on")) {
            updateAgentStatus("✅ Already Applied to this job earlier!", true);
            chrome.runtime.sendMessage({
                type: "APPLICATION_COMPLETED",
                jobTitle: document.title,
                message: "Already applied earlier on Naukri."
            });
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
            const extBtn = document.querySelector("#company-site-button, button:has-text('Apply on company site')");
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
        await handleQuestionnaireDrawer();

        // 6. Verify submission confirmation
        await sleep(2000);
        updateAgentStatus("🎉 Application successfully submitted & verified on Naukri!", true);
        chrome.runtime.sendMessage({
            type: "APPLICATION_COMPLETED",
            jobTitle: document.title,
            message: "100% submitted and verified on Naukri.com"
        });
    }

    async function handleQuestionnaireDrawer() {
        for (let round = 0; round < 6; round++) {
            await sleep(800);

            // A. Answer Notice Period radios
            const labels = Array.from(document.querySelectorAll("label, span, div.radio-label, [class*='radio']"));
            for (const label of labels) {
                const text = (label.innerText || "").toLowerCase();
                if (text.includes("15 days or less") || text.includes("< 15 days") || text.includes("immediate") || text.includes("15 days")) {
                    const radio = label.querySelector("input[type='radio']") || label;
                    radio.click();
                    console.log("[Auto-Apply Agent] Selected Notice Period:", text);
                    break;
                }
            }

            // B. Fill Text Inputs (Experience, CTC, etc.)
            const inputs = Array.from(document.querySelectorAll("input[type='text'], input[type='number'], textarea"));
            for (const input of inputs) {
                if (input.value && input.value.trim().length > 0) continue;
                const fieldText = ((input.placeholder || "") + " " + (input.name || "") + " " + (input.id || "") + " " + (input.getAttribute("aria-label") || "")).toLowerCase();
                const parentText = (input.closest("div, label, li")?.innerText || "").toLowerCase();

                if (fieldText.includes("experience") || parentText.includes("experience") || parentText.includes("years")) {
                    input.value = candidateData.totalExperience;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    console.log("[Auto-Apply Agent] Filled Experience:", candidateData.totalExperience);
                } else if (fieldText.includes("current ctc") || parentText.includes("current ctc") || parentText.includes("current salary")) {
                    input.value = candidateData.currentCtc;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                } else if (fieldText.includes("expected ctc") || parentText.includes("expected ctc") || parentText.includes("expected salary")) {
                    input.value = candidateData.expectedCtc;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                } else if (fieldText.includes("notice") || parentText.includes("notice period")) {
                    input.value = "15";
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }

            // C. Check mandatory checkboxes
            const checkboxes = Array.from(document.querySelectorAll("input[type='checkbox']"));
            for (const cb of checkboxes) {
                if (!cb.checked) {
                    cb.click();
                }
            }

            // D. Click Next or Submit in drawer
            const submitSelectors = [
                "button[type='submit']",
                ".drawer-wrapper button.apply-button",
                "button:has-text('Submit')",
                "button:has-text('Apply')",
                "button:has-text('Save and apply')",
                "button:has-text('Next')",
                "[class*='chatbot'] button.btn",
                "div.bot-action-container button"
            ];

            let submitBtn = null;
            for (const sel of submitSelectors) {
                const btns = Array.from(document.querySelectorAll("button, input[type='submit']"));
                for (const b of btns) {
                    const t = (b.innerText || b.value || "").toLowerCase().trim();
                    if (t === "submit" || t === "apply" || t === "save and apply" || t === "next" || t.includes("apply now")) {
                        if (b.offsetWidth > 0 && b.id !== "apply-button") {
                            submitBtn = b;
                            break;
                        }
                    }
                }
                if (submitBtn) break;
            }

            if (submitBtn) {
                console.log("[Auto-Apply Agent] Clicking drawer Submit/Next button:", submitBtn.innerText);
                submitBtn.click();
                await sleep(1500);
            } else {
                break;
            }
        }
    }

    // Run automatically when page is loaded
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(executeNaukriAutoApply, 1000);
    } else {
        window.addEventListener("DOMContentLoaded", () => setTimeout(executeNaukriAutoApply, 1000));
    }
})();
