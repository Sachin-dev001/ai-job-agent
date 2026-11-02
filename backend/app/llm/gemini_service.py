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
        self.api_key = settings.GEMINI_API_KEY
        self.model_endpoint = "gemini-flash-lite-latest"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 20)

    def generate(self, prompt: str, system_prompt: str = "", json_mode: bool = False, temperature: float = 0.2) -> Optional[str]:
        if not self.is_available():
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_endpoint}:generateContent?key={self.api_key}"
        
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
            res = urllib.request.urlopen(req, timeout=15)
            data = json.loads(res.read().decode())
            candidates = data.get("candidates", [])
            if candidates and candidates[0].get("content", {}).get("parts"):
                return candidates[0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"[Gemini Service] API call failed: {e}")
            return None

        return None

gemini_service = GeminiService()
