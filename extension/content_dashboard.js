// AI Auto-Apply Agent - Dashboard Bridge Content Script
// Bridges communication between Vercel web app and Chrome Extension

console.log("[Auto-Apply Extension] Dashboard Bridge initialized on:", window.location.href);

// Inject global marker and dispatch events WITHOUT creating inline <script> tags (100% CSP-Safe)
function notifyExtensionReady() {
    try {
        document.documentElement.setAttribute("data-autoapply-extension", "true");
        window.postMessage({
            type: "PONG_AUTOAPPLY_EXTENSION",
            installed: true,
            version: "1.0.0"
        }, "*");
        window.dispatchEvent(new CustomEvent("AutoApplyExtensionReady", { detail: { version: "1.0.0" } }));
    } catch (_) {}
}

notifyExtensionReady();
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", notifyExtensionReady);
} else {
    setTimeout(notifyExtensionReady, 300);
}

// Listen for apply requests from web console (app.js)
window.addEventListener("message", (event) => {
    if (!event.data || typeof event.data !== "object") return;

    if (event.data.type === "TRIGGER_EXTENSION_APPLY") {
        console.log("[Auto-Apply Extension Bridge] Received apply command from web app:", event.data.job?.title);
        if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
            chrome.runtime.sendMessage({
                type: "START_AUTO_APPLY",
                job: event.data.job,
                profile: event.data.profile,
                autoClose: event.data.autoClose !== false
            }, (res) => {
                console.log("[Auto-Apply Extension Bridge] Background launch response:", res);
            });
        }
    }

    if (event.data.type === "PING_AUTOAPPLY_EXTENSION") {
        notifyExtensionReady();
    }
});

// Listen for completion messages from extension background worker and forward to web app
if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((message) => {
        if (message.type === "DASHBOARD_APPLICATION_SUCCESS") {
            console.log("[Auto-Apply Extension Bridge] Forwarding success to web app:", message.job?.title);
            window.postMessage({
                type: "EXTENSION_APPLY_SUCCESS",
                job: message.job,
                message: message.message,
                appliedAt: message.appliedAt
            }, "*");
        } else if (message.type === "DASHBOARD_APPLICATION_FAILED") {
            console.log("[Auto-Apply Extension Bridge] Forwarding failure to web app:", message.job?.title);
            window.postMessage({
                type: "EXTENSION_APPLY_FAILED",
                job: message.job,
                reason: message.reason
            }, "*");
        }
    });
}
