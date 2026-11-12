import os
import json
import logging
import httpx
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger("gemini_service")

class GeminiService:
    """
    Direct, robust service for Google AI Studio Gemini API.
    Supports high-speed structured JSON generation and free reasoning with multi-model failover.
    Fully async-ready and non-blocking with httpx client and 25s timeout.
    """

    def __init__(self):
        self.candidate_models = [
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-pro-latest"
        ]

    def get_api_key(self) -> str:
        key = os.getenv("GEMINI_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "") or ""
        return key.strip("'\" \t\r\n")

    def is_available(self) -> bool:
        key = self.get_api_key()
        return bool(key and len(key) > 20)

    def _build_payload(self, prompt: str, system_prompt: str = "", json_mode: bool = False, temperature: float = 0.2) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
        if json_mode:
            payload["generationConfig"]["response_mime_type"] = "application/json"
        return payload

    def generate(self, prompt: str, system_prompt: str = "", json_mode: bool = False, temperature: float = 0.2) -> Optional[str]:
        """
        Synchronous generation with multi-model failover and 25s timeout.
        """
        api_key = self.get_api_key()
        if not api_key:
            return None

        payload = self._build_payload(prompt, system_prompt, json_mode, temperature)

        with httpx.Client(timeout=25.0) as client:
            for model_name in self.candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    res = client.post(url, json=payload, headers={"Content-Type": "application/json"})
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates and isinstance(candidates, list) and len(candidates) > 0:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and isinstance(parts, list) and isinstance(parts[0], dict) and "text" in parts[0]:
                                logger.info(f"[Gemini Service] Success with model: {model_name}")
                                return parts[0]["text"].strip()
                    elif res.status_code in (401, 403):
                        logger.error(f"[Gemini Service] Fatal authentication error ({res.status_code}) on {model_name}. Stopping chain.")
                        break
                    else:
                        logger.warning(f"[Gemini Service] Model {model_name} returned status {res.status_code}: {res.text[:120]}. Failing over to next model.")
                        continue
                except httpx.TimeoutException:
                    logger.warning(f"[Gemini Service] Model {model_name} timed out after 25s. Failing over to next model.")
                    continue
                except Exception as e:
                    logger.warning(f"[Gemini Service] Model {model_name} attempt exception: {e}. Failing over to next model.")
                    continue

        return None

    async def generate_async(self, prompt: str, system_prompt: str = "", json_mode: bool = False, temperature: float = 0.2) -> Optional[str]:
        """
        Fully asynchronous, non-blocking generation with multi-model failover.
        """
        api_key = self.get_api_key()
        if not api_key:
            return None

        payload = self._build_payload(prompt, system_prompt, json_mode, temperature)

        async with httpx.AsyncClient(timeout=25.0) as client:
            for model_name in self.candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    res = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates and isinstance(candidates, list) and len(candidates) > 0:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and isinstance(parts, list) and isinstance(parts[0], dict) and "text" in parts[0]:
                                logger.info(f"[Gemini Service] Success with model: {model_name}")
                                return parts[0]["text"].strip()
                    elif res.status_code in (401, 403):
                        logger.error(f"[Gemini Service] Fatal authentication error ({res.status_code}) on {model_name}. Stopping chain.")
                        break
                    else:
                        logger.warning(f"[Gemini Service] Model {model_name} returned status {res.status_code}: {res.text[:120]}. Failing over to next model.")
                        continue
                except httpx.TimeoutException:
                    logger.warning(f"[Gemini Service] Model {model_name} timed out after 25s. Failing over to next model.")
                    continue
                except Exception as e:
                    logger.warning(f"[Gemini Service] Model {model_name} attempt exception: {e}. Failing over to next model.")
                    continue

        return None

gemini_service = GeminiService()
