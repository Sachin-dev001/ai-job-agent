// AI Auto-Apply Agent - Dashboard Bridge Content Script
// Bridges communication between Vercel web app and Chrome Extension

console.log("[Auto-Apply Extension] Dashboard Bridge initialized on:", window.location.href);

// Inject global flag so frontend knows extension is active
function injectExtensionMarker() {
    try {
        const script = document.createElement("script");
        script.textContent = `
            window.__AUTOAPPLY_EXTENSION_INSTALLED__ = true;
            window.__AUTOAPPLY_EXTENSION_VERSION__ = "1.0.0";
            window.dispatchEvent(new CustomEvent("AutoApplyExtensionReady", { detail: { version: "1.0.0" } }));
            console.log("[Auto-Apply Extension] window.__AUTOAPPLY_EXTENSION_INSTALLED__ set to true");
        `;
        (document.head || document.documentElement).appendChild(script);
        script.remove();
    } catch (e) {
        console.warn("[Auto-Apply Extension] Marker injection note:", e);
    }
}
injectExtensionMarker();
window.addEventListener("DOMContentLoaded", injectExtensionMarker);

// Listen for apply requests from web console (app.js)
window.addEventListener("message", (event) => {
    if (!event.data || typeof event.data !== "object") return;

    if (event.data.type === "TRIGGER_EXTENSION_APPLY") {
        console.log("[Auto-Apply Extension Bridge] Received apply command from web app:", event.data.job?.title);
        chrome.runtime.sendMessage({
            type: "START_AUTO_APPLY",
            job: event.data.job,
            profile: event.data.profile,
            autoClose: event.data.autoClose !== false
        }, (res) => {
            console.log("[Auto-Apply Extension Bridge] Background launch response:", res);
        });
    }

    if (event.data.type === "PING_AUTOAPPLY_EXTENSION") {
        window.postMessage({ type: "PONG_AUTOAPPLY_EXTENSION", version: "1.0.0" }, "*");
    }
});

// Listen for completion messages from extension background worker and forward to web app
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
