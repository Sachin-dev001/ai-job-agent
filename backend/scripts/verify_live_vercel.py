import urllib.request
import time

url = "https://ai-job-agent-frontend-mauve.vercel.app/static/js/app.js"
print(f"Checking {url} ...")

for attempt in range(6):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
        content = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        has_robot = "Robot Active ⚡" in content
        has_autoapply = "executeClientAutoApply" in content
        print(f"Attempt {attempt+1}: Robot Active={has_robot}, autoapply={has_autoapply}")
        if has_robot:
            print("🎉 SUCCESS: Live Vercel frontend has updated with the latest code!")
            break
    except Exception as e:
        print(f"Attempt {attempt+1} error:", e)
    time.sleep(5)
