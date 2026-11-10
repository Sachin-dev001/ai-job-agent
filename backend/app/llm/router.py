import os
from enum import Enum
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from app.config import settings

class TaskType(Enum):
    RESUME_ANALYSIS = "resume_analysis"
    SKILL_EXTRACTION = "skill_extraction"
    JOB_TITLE_MAPPING = "job_title_mapping"
    HTML_PARSING = "html_parsing"
    JOB_MATCHING = "job_matching"
    COVER_LETTER = "cover_letter"
    FORM_FILLING = "form_filling"
    NOTIFICATION = "notification"
    COMPLEX_REASONING = "complex_reasoning"

class LLMRouter:
    def __init__(self):
        self._llms = {}
        self._init_providers()

    def _init_providers(self):
        # 1. Google Gemini Flash
        if settings.GEMINI_API_KEY:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                # Try gemini-flash-lite-latest first, fallback to 2.0-flash
                for m in ["gemini-flash-lite-latest", "gemini-2.0-flash", "gemini-2.5-flash-lite"]:
                    try:
                        self._llms["gemini"] = ChatGoogleGenerativeAI(
                            model=m,
                            google_api_key=settings.GEMINI_API_KEY,
                            temperature=0.2
                        )
                        break
                    except Exception:
                        continue
            except Exception as e:
                print(f"Warning: Failed to load Gemini client: {e}")

        # 2. Groq (Ultra-fast inference with Qwen 27B, GPT-OSS, and LLaMA)
        if settings.GROQ_API_KEY:
            try:
                from langchain_groq import ChatGroq
                # Prioritize available models for this key
                for m70 in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile"]:
                    try:
                        self._llms["groq_70b"] = ChatGroq(
                            model=m70,
                            api_key=settings.GROQ_API_KEY,
                            temperature=0.1
                        )
                        break
                    except Exception:
                        continue

                for m8 in ["openai/gpt-oss-20b", "llama-3.1-8b-instant"]:
                    try:
                        self._llms["groq_8b"] = ChatGroq(
                            model=m8,
                            api_key=settings.GROQ_API_KEY,
                            temperature=0.1
                        )
                        break
                    except Exception:
                        continue
            except Exception as e:
                print(f"Warning: Failed to load Groq client: {e}")

        # 3. Cohere (Classification & Reranking)
        if settings.COHERE_API_KEY:
            try:
                from langchain_cohere import ChatCohere
                self._llms["cohere"] = ChatCohere(
                    model="command-r-plus",
                    cohere_api_key=settings.COHERE_API_KEY,
                    temperature=0.2
                )
            except Exception as e:
                print(f"Warning: Failed to load Cohere client: {e}")

        # 4. Mistral (Lightweight messaging)
        if settings.MISTRAL_API_KEY:
            try:
                from langchain_mistralai import ChatMistralAI
                self._llms["mistral"] = ChatMistralAI(
                    model="mistral-small-latest",
                    api_key=settings.MISTRAL_API_KEY,
                    temperature=0.2
                )
            except Exception as e:
                print(f"Warning: Failed to load Mistral client: {e}")

    def get_llm(self, task: TaskType) -> Optional[BaseChatModel]:
        """
        Routes task to the optimal free LLM with intelligent fallbacks.
        """
        priority_map = {
            TaskType.RESUME_ANALYSIS: ["groq_70b", "gemini"],
            TaskType.SKILL_EXTRACTION: ["groq_70b", "gemini"],
            TaskType.JOB_TITLE_MAPPING: ["groq_70b", "gemini"],
            TaskType.HTML_PARSING: ["groq_70b", "gemini"],
            TaskType.JOB_MATCHING: ["cohere", "groq_70b", "gemini"],
            TaskType.COVER_LETTER: ["gemini", "groq_70b"],
            TaskType.FORM_FILLING: ["groq_8b", "mistral", "groq_70b"],
            TaskType.NOTIFICATION: ["mistral", "groq_8b", "gemini"],
            TaskType.COMPLEX_REASONING: ["gemini", "groq_70b"],
        }

        providers = priority_map.get(task, ["groq_70b", "gemini"])
        for provider in providers:
            if provider in self._llms:
                return self._llms[provider]

        # Return whatever is available as safety net
        if self._llms:
            return next(iter(self._llms.values()))
        return None

router = LLMRouter()
