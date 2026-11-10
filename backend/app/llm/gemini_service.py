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
    Supports high-speed structured JSON generation and free reasoning with multi-model failover.
    """

    def __init__(self):
        self.candidate_models = [
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest",
            "gemini-flash-lite-latest"
        ]

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

        encoded_data = json.dumps(payload).encode("utf-8")

        import urllib.error
        for model_name in self.candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                req = urllib.request.Request(
                    url,
                    data=encoded_data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=4) as res:
                    data = json.loads(res.read().decode())
                candidates = data.get("candidates", [])
                if candidates and isinstance(candidates, list) and len(candidates) > 0:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and isinstance(parts, list) and isinstance(parts[0], dict) and "text" in parts[0]:
                        logger.info(f"[Gemini Service] Success with model: {model_name}")
                        return parts[0]["text"].strip()
            except urllib.error.HTTPError as http_err:
                logger.warning(f"[Gemini Service] Model {model_name} HTTP {http_err.code}: {http_err.reason}")
                if http_err.code in (400, 401, 403):
                    logger.warning(f"[Gemini Service] Fatal authentication or client error ({http_err.code}). Aborting model attempts.")
                    break
                continue
            except Exception as e:
                logger.warning(f"[Gemini Service] Model {model_name} attempt: {e}")
                continue

        return None

gemini_service = GeminiService()
