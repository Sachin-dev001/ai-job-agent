import os
import json
import logging
import groq
from app.config import settings
from app.parsers.document_parser import parse_resume_file
from app.parsers.models import ResumeAnalysisResult, JobTitleRecommendation
from app.llm.gemini_service import gemini_service

logger = logging.getLogger("resume_analyst")

RESUME_EXTRACTION_SYSTEM_PROMPT = """You are an expert technical recruiter and resume analyst.
Extract structured information from the provided resume text.

Output MUST be a single valid JSON object adhering strictly to this schema:
{
  "candidate_name": "Full Name or null",
  "email": "Email address or null",
  "phone": "Phone number or null",
  "skills": ["Python", "FastAPI", "React", "Docker", "Machine Learning"],
  "experience_years": 2.5,
  "education": "Degree and University or null",
  "recommended_job_titles": [
    {
      "title": "AI Engineer",
      "confidence_score": 0.95,
      "reasoning": "Strong match with Python, agent workflows, and machine learning"
    },
    {
      "title": "Python Developer",
      "confidence_score": 0.90,
      "reasoning": "Solid foundation in Python backend frameworks"
    }
  ]
}"""

class ResumeAnalyst:
    def __init__(self):
        pass

    async def analyze(self, file_path: str) -> ResumeAnalysisResult:
        # 1. Parse document text
        raw_text = parse_resume_file(file_path)
        if not raw_text.strip():
            raise ValueError("Could not extract any readable text from the uploaded document.")

        # Keep prompt concise to avoid token exhaustion
        prompt = f"Resume Content:\n-----------------\n{raw_text[:3500]}\n-----------------\nExtract information and output JSON strictly conforming to schema."

        content = None

        # 2. Tier 1: Try Google Gemini Flash Lite (Highest free limits & fast)
        if gemini_service.is_available():
            try:
                content = gemini_service.generate(
                    prompt=prompt,
                    system_prompt=RESUME_EXTRACTION_SYSTEM_PROMPT,
                    json_mode=True,
                    temperature=0.1
                )
                if content:
                    logger.info("[ResumeAnalyst] Successfully extracted resume with Google Gemini Flash")
            except Exception as gemini_err:
                logger.warning(f"[ResumeAnalyst] Gemini attempt error: {gemini_err}")

        # 3. Tier 2: Try Groq with multi-model failover and strict max_tokens (prevents OTPM 429)
        groq_api_key = os.getenv("GROQ_API_KEY", "") or getattr(settings, "GROQ_API_KEY", "") or ""
        groq_api_key = groq_api_key.strip("'\" \t\r\n")

        if not content and groq_api_key:
            client = groq.Groq(api_key=groq_api_key)
            # Models prioritized by high rate-limits & reliable availability
            groq_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

            for model_name in groq_models:
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": RESUME_EXTRACTION_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        max_tokens=700,
                        temperature=0.1
                    )
                    content = response.choices[0].message.content
                    if content and len(content.strip()) > 10:
                        logger.info(f"[ResumeAnalyst] Successfully extracted resume with Groq ({model_name})")
                        break
                except Exception as groq_err:
                    logger.warning(f"[ResumeAnalyst] Groq model '{model_name}' failed: {groq_err}")
                    continue

        if not content:
            raise ValueError("Failed to analyze resume with LLM. Please verify your GEMINI_API_KEY or GROQ_API_KEY.")

        # Clean codeblock fences cleanly using regex
        cleaned_content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE).strip()
        data = json.loads(cleaned_content)

        # Robust field normalization
        if "candidate_name" not in data and "name" in data:
            data["candidate_name"] = data["name"]
        if "skills" not in data:
            data["skills"] = data.get("technical_skills", []) + data.get("soft_skills", [])
        if "experience_years" not in data:
            data["experience_years"] = float(data.get("years_of_experience", 2.0))

        if "recommended_job_titles" in data:
            for item in data["recommended_job_titles"]:
                if "confidence_score" not in item:
                    item["confidence_score"] = float(item.get("match_confidence", 0.9))

        return ResumeAnalysisResult(**data)

resume_analyst = ResumeAnalyst()
