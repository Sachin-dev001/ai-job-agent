document.getElementById("openDashboardBtn").addEventListener("click", () => {
    chrome.tabs.create({ url: "https://ai-job-agent-frontend-mauve.vercel.app/#console" });
});
