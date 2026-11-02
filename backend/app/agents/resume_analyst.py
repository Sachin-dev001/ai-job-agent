import json
from typing import Optional
import groq
from app.config import settings
from app.parsers.models import ResumeAnalysisResult, JobTitleRecommendation
from app.parsers.document_parser import parse_resume_file

RESUME_EXTRACTION_SYSTEM_PROMPT = """You are an elite AI Technical Recruiter and Career Strategist.
Analyze the provided resume text.
You MUST output valid, parseable JSON conforming strictly to this structure:
{
  "candidate_name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "skills": ["string"],
  "experience_years": float,
  "education": "string or null",
  "recommended_job_titles": [
    {
      "title": "string, e.g. AI Engineer, ML Engineer, Python Developer",
      "confidence_score": float between 0.0 and 1.0,
      "reasoning": "brief explanation"
    }
  ]
}
Identify top 3 to 5 industry job titles that best align with their technical skill patterns."""

class ResumeAnalystAgent:
    def __init__(self):
        pass

    async def analyze(self, file_path: str) -> ResumeAnalysisResult:
        # 1. Parse document text
        raw_text = parse_resume_file(file_path)
        if not raw_text.strip():
            raise ValueError("Could not extract any readable text from the uploaded document.")

        # 2. Use Groq with Qwen 27B / Llama high speed JSON model
        client = groq.Groq(api_key=settings.GROQ_API_KEY)
        
        prompt = f"Resume Content:\n-----------------\n{raw_text[:6000]}\n-----------------\nExtract information and output JSON strictly conforming to schema."
        
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
        data = json.loads(content)
        
        # Parse into Pydantic model
        return ResumeAnalysisResult(**data)

resume_analyst = ResumeAnalystAgent()
