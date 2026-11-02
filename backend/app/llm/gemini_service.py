import os
import json
import logging
import urllib.request
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger("gemini_service")

class GeminiService:
    """
    Direct, robust service for Google AI Studio Gemini API.
    Supports high-speed structured JSON generation and free reasoning.
    """

    def __init__(self):
        self.model_endpoint = "gemini-flash-lite-latest"

    def get_api_key(self) -> str:
        key = os.getenv("GEMINI_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "") or ""
        return key.strip("'\" \t\r\n")

    def is_available(self) -> bool:
        key = self.get_api_key()
        return bool(key and len(key) > 20)

    def generate(self, prompt: str, system_prompt: str = "", json_mode: bool = False, temperature: float = 0.2) -> Optional[str]:
        api_key = self.get_api_key()
        if not api_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_endpoint}:generateContent?key={api_key}"
        
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nPlease confirm."}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow all instructions."}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature
            }
        }
        if json_mode:
            payload["generationConfig"]["response_mime_type"] = "application/json"

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            res = urllib.request.urlopen(req, timeout=20)
            data = json.loads(res.read().decode())
            candidates = data.get("candidates", [])
            if candidates and candidates[0].get("content", {}).get("parts"):
                return candidates[0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"[Gemini Service] API call notice: {e}")
            logger.warning(f"[Gemini Service] API call failed: {e}")
            return None

        return None

gemini_service = GeminiService()
