# models.py
from pydantic import BaseModel, Field
from typing import Optional

class JobSearchRequest(BaseModel):
    position: str
    location: Optional[str] = None
    jobNature: Optional[str] = None 
    salary: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[str] = None

class JobResult(BaseModel):
    job_title: str
    company: str
    location: Optional[str] = None
    jobNature: Optional[str] = None  
    experience: Optional[str] = None
    description: Optional[str] = Field(default=None, exclude=True)  # Excluded from output
    apply_link: Optional[str] = None
    salary: Optional[str] = None
    salary_currency: Optional[str] = Field(default=None, exclude=True) 
    min_salary: Optional[str] = Field(default=None, exclude=True) 
    max_salary: Optional[str] = Field(default=None, exclude=True) 
    median_salary: Optional[str] = Field(default=None, exclude=True) 
    source: Optional[str] = Field(default=None, exclude=True)  # Excluded from output
    job_id: Optional[str] = Field(default=None, exclude=True)  # Excluded from output
    relevance_score: Optional[float] = Field(default=None, exclude=True)  # Excluded from output
    matched_skills: Optional[dict] = Field(default=None, exclude=True)  # Store matched skills with confidence scores