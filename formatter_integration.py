# formatter_integration.py
from typing import List, Dict, Any
from pydantic import BaseModel
from models import JobResult

class JobSearchOutputResponse(BaseModel):
    """Final response format for the API"""
    relevant_jobs: List[JobResult]

def format_job_results(jobs: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Format job results to match the required output format.
    
    Args:
        jobs: List of job objects (either JobResult instances or dictionaries)
        
    Returns:
        Dict containing standardized job output
    """
    # Convert jobs to standardized format
    formatted_jobs = []
    
    for job in jobs:
        # Handle both dictionary and object inputs
        if isinstance(job, dict):
            # If job is a dictionary
            job_data = JobResult(
                job_title=job.get("job_title"),
                company=job.get("company"),
                experience=job.get("experience"),
                jobNature=job.get("jobNature"),
                location=job.get("location"),
                salary=job.get("salary"),
                apply_link=job.get("apply_link"),
            )
            
            # Add skills match data if available
            if job.get("matched_skills"):
                job_data.skills_match = {
                    "matched_skills": list(job.get("matched_skills").keys()),
                    "match_percentage": f"{len(job.get('matched_skills')) / len(job.get('matched_skills')) * 100:.0f}%"
                }
        else:
            # If job is an object with attributes
            job_data = JobResult(
                job_title=job.job_title,
                company=job.company,
                experience=job.experience,
                jobNature=job.jobNature,
                location=job.location,
                salary=job.salary,
                apply_link=job.apply_link,
            )
            
            # Add skills match data if available
            if hasattr(job, "matched_skills") and job.matched_skills:
                job_data.skills_match = {
                    "matched_skills": list(job.matched_skills.keys()),
                    "match_percentage": f"{len(job.matched_skills) / len(job.matched_skills) * 100:.0f}%"
                }
        
        formatted_jobs.append(job_data)
    
    # Create the final response object
    response = JobSearchOutputResponse(relevant_jobs=formatted_jobs)
    
    # Convert to dictionary (will exclude fields with exclude=True)
    return response.dict()

def prepare_final_output(jobs: List[JobResult]) -> Dict[str, List[Dict[str, Any]]]:
    """Format job results for API response"""
    output_jobs = []
    
    for job in jobs:
        # Process base job data including salary formatting
        if not job.salary:
            if job.median_salary:
                job.salary = f"Median: ${job.median_salary:,.2f}"
            elif job.min_salary and job.max_salary:
                job.salary = f"${job.min_salary:,.2f} - ${job.max_salary:,.2f}"
            elif job.min_salary:
                job.salary = f"From ${job.min_salary:,.2f}"
            elif job.max_salary:
                job.salary = f"Up to ${job.max_salary:,.2f}"
        
        # Convert to dict and exclude internal fields
        job_dict = job.model_dump(exclude_none=True, exclude_unset=True, exclude={'description', 'source', 'job_id', 'relevance_score'})
        
        # Add matched skills if available
        if hasattr(job, "matched_skills") and job.matched_skills:
            skills_count = len(job.matched_skills.keys())
            total_skills = getattr(job, "total_user_skills", skills_count)  
            
            job_dict["skills_match"] = {
                "matched_skills": list(job.matched_skills.keys()),
                "match_percentage": f"{(skills_count / total_skills) * 100:.0f}%" if total_skills > 0 else "0%"
            }
        
        output_jobs.append(job_dict)
    
    return {"relevant_jobs": output_jobs}