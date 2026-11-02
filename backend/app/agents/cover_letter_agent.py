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
        skills = ", ".join(candidate_data.get("skills", ["Python", "LangGraph", "GenAI", "Machine Learning"]))
        name = candidate_data.get("candidate_name") or "Sachin Sharma"
        exp = candidate_data.get("experience_years", 1.5)

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

        # 1. Try Google Gemini Flash Lite first (via Google AI Studio key)
        if gemini_service.is_available():
            result = gemini_service.generate(
                prompt=user_content,
                system_prompt=COVER_LETTER_SYSTEM_PROMPT,
                temperature=0.3
            )
            if result:
                return result

        # 2. Fallback to Groq
        if settings.GROQ_API_KEY:
            client = groq.Groq(api_key=settings.GROQ_API_KEY)
            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {"role": "system", "content": COVER_LETTER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content

        return f"Dear Hiring Team at {company},\n\nI am writing to express my strong interest in the {job_title} role. With experience in {skills}, I am confident in delivering high impact for your team.\n\nBest regards,\n{name}"

    async def generate_cover_letter(self, **kwargs) -> str:
        candidate_data = {
            "candidate_name": kwargs.get("candidate_name", "Sachin"),
            "skills": kwargs.get("candidate_skills", ["Python", "LangGraph", "FastAPI", "AI Agents"]),
            "experience_years": kwargs.get("experience_years", 2)
        }
        return await self.generate(
            candidate_data=candidate_data,
            job_title=kwargs.get("target_role", "Software Engineer"),
            company=kwargs.get("target_company", "Tech Company"),
            job_description=kwargs.get("job_description", "")
        )

cover_letter_agent = CoverLetterAgent()
