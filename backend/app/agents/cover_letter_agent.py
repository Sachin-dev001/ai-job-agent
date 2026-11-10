import os
import groq
from app.config import settings
from app.llm.gemini_service import gemini_service

COVER_LETTER_SYSTEM_PROMPT = """You are an elite career strategist and technical copywriter.
Generate a concise, compelling cover letter pitch for the candidate applying to the specific role.
Focus on how their skills (Python, LangGraph, LLMs, GenAI, Machine Learning) directly benefit the hiring company.
Provide clean, formatted text without generic placeholders."""

class CoverLetterAgent:
    def __init__(self):
        pass

    async def generate(self, candidate_data: dict, job_title: str, company: str, job_description: str) -> str:
        skills_val = candidate_data.get("skills", ["Python", "AI", "Software Engineering"])
        if isinstance(skills_val, list):
            skills = ", ".join(skills_val)
        else:
            skills = str(skills_val)
        name = candidate_data.get("candidate_name") or "Candidate"
        exp = candidate_data.get("experience_years", 2.0)

        user_content = f"""
Candidate: {name}
Skills: {skills}
Experience: {exp} years

Target Job:
Role: {job_title}
Company: {company}
Overview: {job_description}

Generate a punchy, 3-paragraph tailored cover letter:
1. Enthusiastic introduction & why this role matches candidate's passion.
2. 2-3 specific technical achievements showcasing how LangGraph/Python/LLM agent workflows deliver value.
3. Call to action closing.
"""

        # 1. Tier 1: Try Google Gemini Flash Lite
        if gemini_service.is_available():
            try:
                result = gemini_service.generate(
                    prompt=user_content,
                    system_prompt=COVER_LETTER_SYSTEM_PROMPT,
                    temperature=0.3
                )
                if result and len(result.strip()) > 30:
                    return result
            except Exception as e:
                print(f"[CoverLetterAgent] Gemini attempt notice: {e}")

        # 2. Tier 2: Groq failover with safe token limit
        groq_api_key = os.getenv("GROQ_API_KEY", "") or getattr(settings, "GROQ_API_KEY", "") or ""
        groq_api_key = groq_api_key.strip("'\" \t\r\n")

        if groq_api_key:
            client = groq.Groq(api_key=groq_api_key)
            for model_name in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
                try:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": COVER_LETTER_SYSTEM_PROMPT},
                            {"role": "user", "content": user_content}
                        ],
                        max_tokens=600,
                        temperature=0.3
                    )
                    content = response.choices[0].message.content
                    if content and len(content.strip()) > 30:
                        return content
                except Exception as model_err:
                    print(f"[CoverLetterAgent] Groq {model_name} notice: {model_err}")
                    continue

        return f"Dear Hiring Team at {company},\n\nI am writing to express my strong interest in the {job_title} role. With experience in {skills}, I am confident in delivering high impact for your team.\n\nBest regards,\n{name}"

    async def generate_cover_letter(self, **kwargs) -> str:
        candidate_data = {
            "candidate_name": kwargs.get("candidate_name", "Candidate"),
            "skills": kwargs.get("candidate_skills", ["Python", "FastAPI", "AI Agents"]),
            "experience_years": kwargs.get("experience_years", 2)
        }
        return await self.generate(
            candidate_data=candidate_data,
            job_title=kwargs.get("target_role", "Software Engineer"),
            company=kwargs.get("target_company", "Tech Company"),
            job_description=kwargs.get("job_description", "")
        )

cover_letter_agent = CoverLetterAgent()
