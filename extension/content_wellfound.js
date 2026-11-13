// AI Auto-Apply Agent - Wellfound Autonomous Content Script
// Automatically detects apply buttons, fills recruiter pitch, answers screening questions, and submits on Wellfound

(function () {
    console.log("[Auto-Apply Agent] Wellfound Content script injected on:", window.location.href);

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    let candidateData = {
        name: "Sachin Sharma",
        totalExperience: "3.5",
        noticePeriod: "15 Days or less",
        currentCtc: "12",
        expectedCtc: "18",
        skills: ["Python", "FastAPI", "React", "AI Agents", "Docker"]
    };

    // Load candidate profile from storage if available
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        try {
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
        } catch (_) {}
    }

    async function executeWellfoundAutoApply() {
        await sleep(1500);

        // 1. Check if already applied
        const bodyText = (document.body.innerText || "").toLowerCase();
        if (bodyText.includes("already applied") || bodyText.includes("applied on") || bodyText.includes("application submitted")) {
            console.log("[Auto-Apply Agent] Already applied on Wellfound.");
            if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    type: "APPLICATION_COMPLETED",
                    jobTitle: document.title,
                    message: "Already applied earlier on Wellfound."
                });
            }
            return;
        }

        // 2. Locate Apply button
        const applyBtn = Array.from(document.querySelectorAll("button, a")).find(el => {
            const t = (el.innerText || "").toLowerCase().trim();
            return (t === "apply" || t === "apply now" || t.includes("quick apply")) && el.offsetWidth > 0;
        });

        if (!applyBtn) {
            console.log("[Auto-Apply Agent] Apply button not found on Wellfound page.");
            return;
        }

        console.log("[Auto-Apply Agent] Clicking Wellfound Apply button...");
        applyBtn.scrollIntoView({ behavior: "smooth", block: "center" });
        applyBtn.click();
        await sleep(1800);

        // 3. Fill recruiter note / cover letter textarea
        const noteArea = document.querySelector("textarea[name='userNote'], textarea[placeholder*='note'], textarea");
        if (noteArea && (!noteArea.value || noteArea.value.trim().length === 0)) {
            const pitch = `Hi Hiring Team,\n\nI am very excited to apply for this position! I have extensive experience in Python, GenAI, LLMs, and building high-performance production systems. I am immediately available for interviews.\n\nBest regards,\n${candidateData.name}`;
            noteArea.value = pitch;
            noteArea.dispatchEvent(new Event("input", { bubbles: true }));
            noteArea.dispatchEvent(new Event("change", { bubbles: true }));
            console.log("[Auto-Apply Agent] Filled Wellfound recruiter note.");
        }

        // 4. Answer screening questions / radios
        const radioGroups = {};
        const allRadios = Array.from(document.querySelectorAll("input[type='radio']"));
        for (const r of allRadios) {
            const groupKey = r.name || (r.closest("fieldset, div[role='radiogroup']")?.id) || "default_group";
            if (!radioGroups[groupKey]) radioGroups[groupKey] = [];
            radioGroups[groupKey].push(r);
        }

        for (const key in radioGroups) {
            const radios = radioGroups[key];
            const container = radios[0].closest("fieldset, div, [role='group'], form, body") || document.body;
            const contextText = (container.innerText || "").toLowerCase();

            // Default to affirmative (Yes) unless it is visa sponsorship
            let targetIsYes = true;
            if (contextText.includes("visa") || contextText.includes("sponsorship") || contextText.includes("require sponsorship")) {
                targetIsYes = false; // "Do you require sponsorship?" -> No
            }

            let matchedRadio = null;
            for (const r of radios) {
                const label = r.closest("label") || (r.id ? document.querySelector(`label[for='${r.id}']`) : null) || r.parentElement;
                const val = ((r.value || "") + " " + (label?.innerText || "")).toLowerCase().trim();
                if (targetIsYes && (val.includes("yes") || val === "1" || val.includes("true"))) {
                    matchedRadio = r;
                    break;
                } else if (!targetIsYes && (val.includes("no") || val === "0" || val.includes("false"))) {
                    matchedRadio = r;
                    break;
                }
            }

            if (matchedRadio) {
                matchedRadio.checked = true;
                matchedRadio.dispatchEvent(new Event("change", { bubbles: true }));
                matchedRadio.dispatchEvent(new Event("input", { bubbles: true }));
                matchedRadio.click();
                console.log(`[Auto-Apply Agent] Selected ${targetIsYes ? "YES" : "NO"} for radio group '${key}'`);
            }
        }

        // Fill text and numeric inputs
        const inputs = Array.from(document.querySelectorAll("input[type='text'], input[type='number']"));
        for (const input of inputs) {
            if (!input.value || input.value.trim().length === 0) {
                const name = ((input.name || "") + " " + (input.placeholder || "")).toLowerCase();
                if (name.includes("exp") || name.includes("year")) {
                    input.value = candidateData.totalExperience;
                } else if (name.includes("salary") || name.includes("ctc")) {
                    input.value = candidateData.expectedCtc;
                } else {
                    input.value = candidateData.totalExperience;
                }
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }

        // Check required checkboxes
        const checkboxes = Array.from(document.querySelectorAll("input[type='checkbox']"));
        for (const cb of checkboxes) {
            if (!cb.checked) {
                cb.checked = true;
                cb.dispatchEvent(new Event("change", { bubbles: true }));
                cb.click();
            }
        }

        await sleep(1000);

        // 5. Click final Send Application / Submit button
        const sendBtn = Array.from(document.querySelectorAll("button, input[type='submit']")).find(el => {
            const t = (el.innerText || el.value || "").toLowerCase().trim();
            return (t.includes("send application") || t.includes("submit application") || t === "send" || t === "submit") && el.offsetWidth > 0;
        });

        if (sendBtn) {
            console.log("[Auto-Apply Agent] Submitting Wellfound application:", sendBtn.innerText);
            sendBtn.scrollIntoView({ behavior: "smooth", block: "center" });
            sendBtn.click();
            await sleep(2000);

            if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
                chrome.runtime.sendMessage({
                    type: "APPLICATION_COMPLETED",
                    jobTitle: document.title,
                    message: "Submitted successfully on Wellfound!"
                });
            }
        }
    }

    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(executeWellfoundAutoApply, 1200);
    } else {
        window.addEventListener("DOMContentLoaded", () => setTimeout(executeWellfoundAutoApply, 1200));
    }
})();
