// AI Auto-Apply Agent - Background Service Worker
// Manages application queues and tab automation for Naukri & Wellfound

let activeApplyTasks = {};

// Listen for messages from dashboard and job tabs
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("[Auto-Apply Background] Message received:", message.type, message);

    if (message.type === "PING_EXTENSION") {
        sendResponse({ status: "alive", version: "1.0.0" });
        return true;
    }

    if (message.type === "START_AUTO_APPLY") {
        const { job, profile, autoClose = true } = message;
        if (!job || !job.job_url) {
            sendResponse({ status: "error", message: "Invalid job payload" });
            return true;
        }

        // Save profile in storage for content scripts
        chrome.storage.local.set({ candidateProfile: profile || {} });

        // Open target job in a new focused or background tab
        chrome.tabs.create({ url: job.job_url, active: true }, (tab) => {
            activeApplyTasks[tab.id] = {
                job: job,
                profile: profile,
                dashboardTabId: sender.tab ? sender.tab.id : null,
                autoClose: autoClose,
                startedAt: Date.now()
            };
            console.log(`[Auto-Apply Background] Launched automation tab ${tab.id} for: ${job.title}`);
            sendResponse({ status: "launched", tabId: tab.id, jobTitle: job.title });
        });
        return true;
    }

    if (message.type === "APPLICATION_COMPLETED") {
        const tabId = sender.tab ? sender.tab.id : null;
        const task = tabId ? activeApplyTasks[tabId] : null;

        console.log(`[Auto-Apply Background] Application confirmed for: ${message.jobTitle}`, message);

        // Notify dashboard tab
        if (task && task.dashboardTabId) {
            chrome.tabs.sendMessage(task.dashboardTabId, {
                type: "DASHBOARD_APPLICATION_SUCCESS",
                job: task.job,
                message: message.message || "Applied successfully!",
                appliedAt: new Date().toISOString()
            }).catch(() => {});
        }

        // Auto-close job tab after 2.5s if requested
        if (tabId && task && task.autoClose) {
            setTimeout(() => {
                chrome.tabs.remove(tabId).catch(() => {});
                delete activeApplyTasks[tabId];
            }, 2500);
        }

        sendResponse({ status: "recorded" });
        return true;
    }

    if (message.type === "APPLICATION_FAILED") {
        const tabId = sender.tab ? sender.tab.id : null;
        const task = tabId ? activeApplyTasks[tabId] : null;

        if (task && task.dashboardTabId) {
            chrome.tabs.sendMessage(task.dashboardTabId, {
                type: "DASHBOARD_APPLICATION_FAILED",
                job: task.job,
                reason: message.reason || "Apply action needed"
            }).catch(() => {});
        }
        sendResponse({ status: "notified" });
        return true;
    }

    return true;
});

// Clean up closed tabs
chrome.tabs.onRemoved.addListener((tabId) => {
    if (activeApplyTasks[tabId]) {
        delete activeApplyTasks[tabId];
    }
});
