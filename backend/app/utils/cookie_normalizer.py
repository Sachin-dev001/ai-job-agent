"""
Utilities for normalizing and validating browser session cookies across platforms (Naukri, Wellfound).
Supports:
- Standard JSON array of cookie objects (Playwright / Puppeteer format)
- Dictionary with 'cookies' array
- Key-Value dictionary { name: value }
- Raw HTTP Cookie Header string ("name=val; name2=val2")
- Netscape HTTP cookie file format (tab/space-delimited)
"""
import json
import re
from typing import Any, Dict, List, Optional


def _is_netscape_format(lines: List[str]) -> bool:
    for line in lines:
        if line.startswith("# Netscape") or line.startswith("# HTTP Cookie File"):
            return True
        parts = line.split("\t") if "\t" in line else line.split()
        if (
            len(parts) >= 7
            and parts[1].upper() in ["TRUE", "FALSE"]
            and parts[3].upper() in ["TRUE", "FALSE"]
            and parts[4].isdigit()
        ):
            return True
    return False


def normalize_cookies(raw_data: Any, platform: str = "naukri") -> List[Dict[str, Any]]:
    """
    Transforms any valid cookie representation into a normalized list of Playwright-compatible cookie dictionaries:
    [
        {"name": "...", "value": "...", "domain": "...", "path": "/"}
    ]
    Returns an empty list if no valid cookies are extracted.
    """
    clean_platform = (platform or "naukri").lower().strip()
    default_domain = f".{clean_platform}.com"
    normalized: List[Dict[str, Any]] = []

    if raw_data is None:
        return []

    # Case 1: String input (JSON string, HTTP Header string, or Netscape format)
    if isinstance(raw_data, str):
        raw_str = raw_data.strip()
        if not raw_str:
            return []

        # If wrapped in quotes due to double-stringification
        if (raw_str.startswith('"') and raw_str.endswith('"')) or (raw_str.startswith("'") and raw_str.endswith("'")):
            try:
                unwrapped = json.loads(raw_str)
                if not isinstance(unwrapped, str):
                    return normalize_cookies(unwrapped, clean_platform)
                raw_str = unwrapped.strip()
            except Exception:
                raw_str = raw_str[1:-1].strip()

        # Try parsing as JSON first
        try:
            parsed = json.loads(raw_str)
            return normalize_cookies(parsed, clean_platform)
        except Exception:
            pass

        # Check for Netscape HTTP Cookie file format
        lines = [line.strip() for line in raw_str.splitlines() if line.strip() and not line.strip().startswith("#")]
        if _is_netscape_format(lines):
            for line in lines:
                parts = line.split("\t") if "\t" in line else line.split()
                if len(parts) >= 7:
                    c_domain = parts[0]
                    c_path = parts[2]
                    c_name = parts[5]
                    c_val = parts[6]
                    if c_name and c_val:
                        normalized.append({
                            "name": str(c_name).strip(),
                            "value": str(c_val).strip(),
                            "domain": str(c_domain).strip() if str(c_domain).strip().startswith(".") else f".{str(c_domain).strip()}",
                            "path": str(c_path).strip() or "/"
                        })
                elif len(parts) >= 2 and not parts[0].lower().startswith("cookie:"):
                    k = parts[-2].strip()
                    v = parts[-1].strip()
                    if k and v and "=" not in k:
                        normalized.append({
                            "name": k,
                            "value": v,
                            "domain": default_domain,
                            "path": "/"
                        })
            if normalized:
                return normalized

        # Parse HTTP header cookie string format: 'name=val; name2=val2' or multi-line
        chunks = []
        for line in raw_str.splitlines():
            # If line starts with "Cookie:" or "cookie:" or "set-cookie:", strip it
            clean_line = re.sub(r"^(cookie|set-cookie):\s*", "", line.strip(), flags=re.IGNORECASE)
            chunks.extend([c.strip() for c in clean_line.split(";") if c.strip()])

        for chunk in chunks:
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                k, v = k.strip(), v.strip()
                # Skip HTTP header cookie attributes
                if k.lower() in ["path", "domain", "expires", "max-age", "samesite", "priority", "secure", "httponly"]:
                    continue
                if k and v:
                    normalized.append({
                        "name": k,
                        "value": v,
                        "domain": default_domain,
                        "path": "/"
                    })
        return normalized

    # Case 2: Dict input
    if isinstance(raw_data, dict):
        # Case 2a: Dict with 'cookies' list (e.g. Playwright storageState or Chrome export wrapper)
        if "cookies" in raw_data and isinstance(raw_data["cookies"], list):
            return normalize_cookies(raw_data["cookies"], clean_platform)

        # Case 2b: Dict representing a single cookie object: {"name": "...", "value": "..."}
        k = raw_data.get("name") or raw_data.get("key")
        v = raw_data.get("value") or raw_data.get("val")
        if k and v is not None:
            c_domain = str(raw_data.get("domain") or default_domain).strip()
            if not c_domain.startswith("."):
                c_domain = f".{c_domain}"
            return [{
                "name": str(k).strip(),
                "value": str(v).strip(),
                "domain": c_domain,
                "path": str(raw_data.get("path") or "/")
            }]

        # Case 2c: Key-value map of cookies: {"session_id": "xyz", "auth_token": "abc"}
        for k_item, v_item in raw_data.items():
            if k_item and v_item is not None and not isinstance(v_item, (dict, list)):
                normalized.append({
                    "name": str(k_item).strip(),
                    "value": str(v_item).strip(),
                    "domain": default_domain,
                    "path": "/"
                })
        return normalized

    # Case 3: List input
    if isinstance(raw_data, list):
        for item in raw_data:
            if isinstance(item, dict):
                k = item.get("name") or item.get("key")
                v = item.get("value") or item.get("val")
                if k and v is not None:
                    c_domain = str(item.get("domain") or default_domain).strip()
                    if not c_domain.startswith("."):
                        c_domain = f".{c_domain}"
                    normalized.append({
                        "name": str(k).strip(),
                        "value": str(v).strip(),
                        "domain": c_domain,
                        "path": str(item.get("path") or "/")
                    })
            elif isinstance(item, str) and "=" in item:
                # Array of "k=v" strings
                k, v = item.split("=", 1)
                k, v = k.strip(), v.strip()
                if k and v:
                    normalized.append({
                        "name": k,
                        "value": v,
                        "domain": default_domain,
                        "path": "/"
                    })
        return normalized

    return []
