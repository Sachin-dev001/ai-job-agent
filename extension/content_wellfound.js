// AI Auto-Apply Agent - Wellfound Autonomous Content Script
// Automatically detects apply buttons, fills note pitch, and submits on Wellfound

(function () {
    console.log("[Auto-Apply Agent] Wellfound Content script injected on:", window.location.href);

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function executeWellfoundAutoApply() {
        await sleep(1500);

        // Check if Apply button exists
        const applyBtn = Array.from(document.querySelectorAll("button, a")).find(el => {
            const t = (el.innerText || "").toLowerCase().trim();
            return t === "apply" || t === "apply now" || t.includes("quick apply");
        });

        if (applyBtn && applyBtn.offsetWidth > 0) {
            console.log("[Auto-Apply Agent] Clicking Wellfound Apply button...");
            applyBtn.click();
            await sleep(1500);

            // Fill recruiter note if note textarea exists
            const noteArea = document.querySelector("textarea[name='userNote'], textarea[placeholder*='note'], textarea");
            if (noteArea && (!noteArea.value || noteArea.value.trim().length === 0)) {
                chrome.storage.local.get(["candidateProfile"], (res) => {
                    const name = res?.candidateProfile?.candidate_name || "Candidate";
                    noteArea.value = `Hi,\n\nI am very excited about this role! I have strong hands-on experience building AI agents and scalable backend services.\n\nBest regards,\n${name}`;
                    noteArea.dispatchEvent(new Event("input", { bubbles: true }));
                    noteArea.dispatchEvent(new Event("change", { bubbles: true }));
                });
            }

            await sleep(800);

            // Click final Send Application button
            const sendBtn = Array.from(document.querySelectorAll("button")).find(el => {
                const t = (el.innerText || "").toLowerCase().trim();
                return t.includes("send application") || t.includes("submit application") || t === "send";
            });

            if (sendBtn) {
                console.log("[Auto-Apply Agent] Submitting Wellfound application...");
                sendBtn.click();
                await sleep(1500);

                chrome.runtime.sendMessage({
                    type: "APPLICATION_COMPLETED",
                    jobTitle: document.title,
                    message: "Submitted on Wellfound!"
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
