import pytest
import sys
from pathlib import Path

# Add backend and project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.cookie_normalizer import normalize_cookies, _filter_waf_cookies


def test_normalize_dict_list():
    raw_cookies = [
        {"name": "session_id", "value": "test_123", "domain": ".naukri.com", "path": "/"},
        {"name": "user_id", "value": "user_456"}
    ]
    normalized = normalize_cookies(raw_cookies, platform="naukri")
    assert len(normalized) == 2
    assert normalized[0]["name"] == "session_id"
    assert normalized[0]["value"] == "test_123"
    assert normalized[1]["name"] == "user_id"
    assert normalized[1]["domain"] == ".naukri.com"


def test_filter_waf_cookies():
    raw_cookies = [
        {"name": "valid_session", "value": "xyz"},
        {"name": "_abck", "value": "akamai_fingerprint"},
        {"name": "bm_sz", "value": "akamai_bot_metric"},
        {"name": "ak_bmsc", "value": "akamai_cookie"}
    ]
    filtered = _filter_waf_cookies(raw_cookies, platform="naukri")
    assert len(filtered) == 1
    assert filtered[0]["name"] == "valid_session"


def test_normalize_key_value_dict():
    raw_cookies = {"auth_token": "secret_abc", "theme": "dark"}
    normalized = normalize_cookies(raw_cookies, platform="linkedin")
    assert len(normalized) == 2
    names = {c["name"] for c in normalized}
    assert "auth_token" in names
    assert "theme" in names
    assert all(c["domain"] == ".linkedin.com" for c in normalized)


def test_normalize_header_string():
    raw_header = "csrftoken=csrf_val; sessionid=sess_val"
    normalized = normalize_cookies(raw_header, platform="wellfound")
    assert len(normalized) == 2
    names = {c["name"] for c in normalized}
    assert "csrftoken" in names
    assert "sessionid" in names
    assert all(c["domain"] == ".wellfound.com" for c in normalized)
