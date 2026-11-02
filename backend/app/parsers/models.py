from pydantic import BaseModel, Field
from typing import List, Optional

class JobTitleRecommendation(BaseModel):
    title: str = Field(description="Recommended job title based on skills, e.g. AI Engineer")
    confidence_score: float = Field(description="Confidence percentage score between 0.0 and 1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Brief explanation of why this title matches the candidate's profile")

class ResumeAnalysisResult(BaseModel):
    candidate_name: Optional[str] = Field(default=None, description="Candidate's full name")
    email: Optional[str] = Field(default=None, description="Contact email address")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    skills: List[str] = Field(description="List of extracted technical and domain skills")
    experience_years: Optional[float] = Field(default=0.0, description="Estimated total professional experience in years")
    education: Optional[str] = Field(default=None, description="Highest degree or university information")
    recommended_job_titles: List[JobTitleRecommendation] = Field(description="List of top 3 to 5 matching job titles ranked by relevance")
