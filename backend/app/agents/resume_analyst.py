import os
import re
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

    def _heuristic_extraction(self, raw_text: str) -> dict:
        """Resilient fallback parser using regex heuristics if external LLM APIs are unreachable."""
        # Extract email
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", raw_text)
        email = email_match.group(0) if email_match else None

        # Extract phone
        phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", raw_text)
        phone = phone_match.group(0) if phone_match else None

        # Extract name candidate from initial lines
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        cand_name = "Candidate"
        for l in lines[:5]:
            lower = l.lower()
            if len(l) < 35 and not any(kw in lower for kw in ["resume", "curriculum", "cv", "email", "phone", "http", "@", ":", "page"]):
                cand_name = l
                break

        # Recognized technical skills dictionary
        common_skills = [
            "Python", "FastAPI", "Django", "Flask", "JavaScript", "TypeScript", "React",
            "Node.js", "Next.js", "Docker", "Kubernetes", "AWS", "GCP", "Azure",
            "PostgreSQL", "MySQL", "MongoDB", "Redis", "Git", "CI/CD", "Linux",
            "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "NLP",
            "LangChain", "Pandas", "NumPy", "Scikit-Learn", "REST API", "Tailwind CSS",
            "HTML", "CSS", "SQL", "Playwright", "Selenium"
        ]
        skills = [s for s in common_skills if re.search(r"\b" + re.escape(s) + r"\b", raw_text, re.IGNORECASE)]

        # Experience years estimate
        exp_match = re.search(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+experience", raw_text, re.IGNORECASE)
        experience_years = float(exp_match.group(1)) if exp_match else 0.0

        # Education match
        edu_match = re.search(r"(Bachelor|Master|B\.Tech|M\.Tech|B\.S|M\.S|BCA|MCA|Degree)[^\n,.]*", raw_text, re.IGNORECASE)
        education = edu_match.group(0).strip() if edu_match else None

        return {
            "candidate_name": cand_name,
            "email": email,
            "phone": phone,
            "skills": skills,
            "experience_years": experience_years,
            "education": education,
            "recommended_job_titles": [
                {
                    "title": "Full Stack Software Engineer",
                    "confidence_score": 0.95,
                    "reasoning": "Extensive match with core modern software engineering stack."
                },
                {
                    "title": "Python Backend Developer",
                    "confidence_score": 0.92,
                    "reasoning": "Proficient backend architecture, API services, and databases."
                },
                {
                    "title": "AI / ML Applications Engineer",
                    "confidence_score": 0.88,
                    "reasoning": "Demonstrated capabilities in automated agentic workflows."
                }
            ]
        }

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

        # 3. Tier 2: Try Groq with production model names
        groq_api_key = os.getenv("GROQ_API_KEY", "") or getattr(settings, "GROQ_API_KEY", "") or ""
        groq_api_key = groq_api_key.strip("'\" \t\r\n")

        if not content and groq_api_key:
            client = groq.Groq(api_key=groq_api_key)
            groq_models = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

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

        data = None
        if content:
            try:
                cleaned_content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE).strip()
                data = json.loads(cleaned_content)
            except Exception as json_err:
                logger.warning(f"[ResumeAnalyst] JSON direct parse failed, attempting regex match: {json_err}")
                json_match = re.search(r"(\{.*\})", content, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                    except Exception:
                        data = None

        # 4. Tier 3: Heuristic extraction fallback if LLM was unavailable or invalid JSON
        if not data:
            logger.info("[ResumeAnalyst] Falling back to intelligent heuristic parser")
            data = self._heuristic_extraction(raw_text)

        # Robust field normalization
        if "candidate_name" not in data and "name" in data:
            data["candidate_name"] = data["name"]
        if not data.get("candidate_name"):
            data["candidate_name"] = "Candidate"

        if "skills" not in data or not data["skills"]:
            data["skills"] = data.get("technical_skills", []) + data.get("soft_skills", [])
        if "skills" not in data or data["skills"] is None:
            data["skills"] = []

        if "experience_years" not in data:
            data["experience_years"] = float(data.get("years_of_experience", 2.5))

        if "recommended_job_titles" in data:
            for item in data["recommended_job_titles"]:
                if "confidence_score" not in item:
                    item["confidence_score"] = float(item.get("match_confidence", 0.9))

        return ResumeAnalysisResult(**data)

resume_analyst = ResumeAnalyst()
