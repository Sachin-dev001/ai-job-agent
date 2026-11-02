import os
import json
import groq
from app.config import settings
from app.parsers.document_parser import parse_resume_file
from app.parsers.models import ResumeAnalysisResult, JobTitleRecommendation
from app.llm.gemini_service import gemini_service

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

        prompt = f"Resume Content:\n-----------------\n{raw_text[:6000]}\n-----------------\nExtract information and output JSON strictly conforming to schema."

        content = None
        # 2. Try Google Gemini Flash Lite first (via Google AI Studio key)
        if gemini_service.is_available():
            content = gemini_service.generate(
                prompt=prompt,
                system_prompt=RESUME_EXTRACTION_SYSTEM_PROMPT,
                json_mode=True,
                temperature=0.1
            )

        # 3. Fallback to Groq if Gemini is not available or failed
        if not content and settings.GROQ_API_KEY:
            client = groq.Groq(api_key=settings.GROQ_API_KEY)
            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {"role": "system", "content": RESUME_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content

        if not content:
            raise ValueError("Failed to analyze resume with LLM. Please check your GEMINI_API_KEY or GROQ_API_KEY.")

        data = json.loads(content)

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
