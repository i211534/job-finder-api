# googlejobs_scraper.py
from typing import List
import httpx
import logging
import os
from dotenv import load_dotenv
from functions import is_salary_in_range
from models import JobResult, JobSearchRequest
from rate_limiter import RateLimiter
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GoogleJobsAPIScraper:
    """API-based scraper for Google Jobs using Jobs API v14"""
    
    def __init__(self):
        self.api_key = os.environ.get("JOBS_API_KEY", "798b712dd9mshde9f384c5a5b7cfp1eb940jsnab6dc7258b30")
        self.api_host = "jobs-api14.p.rapidapi.com"
        
        if not self.api_key:
            logger.warning("Jobs API key not found. Using default key.")
        
        self.rate_limiter = RateLimiter()

    async def search(self, params: JobSearchRequest, limit: int = 5) -> List[JobResult]:
        logger.info(f"Searching Google Jobs via Jobs API v14 (limit: {limit})")
        if not self.api_key:
            logger.error("Jobs API key not available. Cannot search for Google Jobs.")
            return []

        try:
            # Build search query
            query = params.position
            location = params.location or "United States"
            
            url = "https://jobs-api14.p.rapidapi.com/v2/list"
            
            # Configure employment types
            employment_types = []
            if params.jobNature:
                job_type_map = {
                    "onsite": None,
                    "remote": None  # Handled separately
                }
                job_type = job_type_map.get(params.jobNature.lower())
                if job_type:
                    employment_types.append(job_type)
            
            # Default to all employment types if none specified
            if not employment_types:
                employment_types = ["fulltime", "parttime", "intern", "contractor"]
            
            remote_only = "true" if params.jobNature and params.jobNature.lower() == "remote" else "false"
            
            # Build query parameters
            querystring = {
                "query": query,
                "location": location,
                "autoTranslateLocation": "true",
                "remoteOnly": remote_only,
                "employmentTypes": ";".join(employment_types)
            }

            headers = {
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": self.api_host
            }

            # Parse user's salary range if provided
            user_min_salary = None
            user_max_salary = None
            if params.salary:
                salary_match = re.search(r'(\d+(?:,\d+)?)\s*-\s*(\d+(?:,\d+)?)', params.salary)
                if salary_match:
                    user_min_salary = float(salary_match.group(1).replace(',', ''))
                    user_max_salary = float(salary_match.group(2).replace(',', ''))
                   # logger.info(f"User salary range: {user_min_salary} - {user_max_salary}")

            async def make_googlejobs_request():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=headers, params=querystring)
                    if response.status_code != 200:
                        logger.error(f"Jobs API v14 returned status code {response.status_code} for Google Jobs")
                        if response.status_code == 429:
                            raise httpx.HTTPStatusError(f"Rate limit exceeded: {response.status_code}", request=response.request, response=response)
                        return {}
                    return response.json()
            
            # Use the rate limiter for the API call
            data = await self.rate_limiter.execute_with_retry("jobs_api", make_googlejobs_request)

            results = []
            # Process the API response format
            for raw in data.get("jobs", []):
                
                try:
                    # Prepare description - some APIs provide truncated descriptions
                    description = raw.get("description", "")
                    if isinstance(description, str) and len(description) > 10:
                        parsed_description = description
                    else:
                        parsed_description = f"Position: {raw.get('title', '')}\nCompany: {raw.get('company', '')}"
                    
                    # Format salary information
                    salary_info = ""
                    if raw.get("salary_min") and raw.get("salary_max"):
                        salary_info = f"{raw.get('salary_min')} - {raw.get('salary_max')} {raw.get('salary_currency', 'USD')}"
                    elif raw.get("salary_min"):
                        salary_info = f"{raw.get('salary_min')} {raw.get('salary_currency', 'USD')}"
                    elif raw.get("salary"):
                        salary_info = str(raw.get("salary"))
                    elif raw.get("salaryRange"):
                        salary_info = raw.get("salaryRange")
                    
                    # Check if job salary is within user's requested range
                    if user_min_salary and user_max_salary and salary_info:
                        if not is_salary_in_range(salary_info, user_min_salary, user_max_salary):
                            # Skip this job if salary doesn't match user's range
                            continue
                    
                    # Format location
                    location = raw.get("location", "")
                    if not location and raw.get("city") and raw.get("country"):
                        location = f"{raw.get('city')}, {raw.get('country')}"
                    
                    # Determine job nature (remote/onsite) based on user request and job data
                    requested_job_nature = params.jobNature.lower() if params.jobNature else None
                    
                    # Check for remote indicators in title or description
                    has_remote_indicators = "remote" in raw.get("title", "").lower() or "remote" in parsed_description.lower()[:200]
                    
                    # Determine job nature
                    if requested_job_nature == "remote":
                        # If user requested remote jobs, only include jobs with remote indicators
                        job_nature = "remote"
                        if not has_remote_indicators and remote_only != "true":
                            # Skip this job if it doesn't match the remote criteria
                            continue
                    elif requested_job_nature == "onsite":
                        # If user requested onsite jobs, only include jobs without remote indicators
                        job_nature = "onsite"
                        if has_remote_indicators:
                            # Skip this job if it has remote indicators
                            continue
                    else:
                        # If no specific job nature requested, classify based on indicators
                        job_nature = "remote" if has_remote_indicators else "onsite"
                    
                    # Ensure apply_link is never empty
                    apply_link = raw.get("url", "")
                    if not apply_link:
                        # Fallback URL if the API doesn't provide one
                        job_title = raw.get("title", "").replace(" ", "+")
                        company = raw.get("company", "").replace(" ", "+")
                        apply_link = f"https://www.google.com/search?q={job_title}+{company}+job"
                    
                    results.append(
                        JobResult(
                            job_title=raw.get("title", ""),
                            company=raw.get("company", ""),
                            location=location or "Not specified",
                            salary=salary_info,
                            jobNature=job_nature,
                            experience = "",
                            apply_link=apply_link,
                            description=parsed_description,
                            job_id=str(raw.get("id", "")),
                            source="Google Jobs"
                        )
                    )
                    pass
                except Exception as e:
                    logger.error(f"Error parsing job data from Jobs API v14: {str(e)}")

           # logger.info(f"Found {len(results)} jobs via Google Jobs API after filtering")
            return results[:limit]  # Return only up to the limit

        except Exception as e:
            logger.error(f"Error searching Google Jobs via API: {str(e)}")
            return []