#!/usr/bin/env python3
"""
Sync Local Job Portal Cookies to Render Cloud Backend
Usage: python sync_cookies_to_cloud.py [OPTIONAL_BACKEND_URL]
"""
import os
import sys
import json
import urllib.request
import urllib.error

DEFAULT_BACKEND = "https://autoapply-backend-hvdm.onrender.com"

def sync_platform(backend_url: str, platform: str, cookie_filename: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cookie_path = os.path.join(script_dir, "backend", "cookies", cookie_filename)
    
    if not os.path.exists(cookie_path):
        print(f"[-] {platform}: Cookie file not found at {cookie_path}. Skipping.")
        return False

    try:
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
    except Exception as e:
        print(f"[!] {platform}: Failed to read {cookie_path}: {e}")
        return False

    url = f"{backend_url.rstrip('/')}/api/session/connect-cookies"
    payload = json.dumps({
        "platform": platform,
        "cookies": cookies
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            print(f"[+] {platform.capitalize()}: {res_data.get('message', 'Session connected!')}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"[!] {platform}: HTTP Error {e.code}: {body}")
        return False
    except Exception as e:
        print(f"[!] {platform}: Connection error: {e}")
        return False

def main():
    backend_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BACKEND
    print(f"[*] Syncing session cookies to: {backend_url}")
    sync_platform(backend_url, "naukri", "naukri_cookies.json")
    sync_platform(backend_url, "wellfound", "wellfound_cookies.json")

if __name__ == "__main__":
    main()
