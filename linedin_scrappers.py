# Job scrapers
import logging
import os
import re
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import httpx
from functions import format_experience, get_estimated_salary, map_experience_to_requirements
from models import JobResult, JobSearchRequest
from rate_limiter import RateLimiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rate_limiter = RateLimiter()

class LinkedInAPIScraper:
    """API-based scraper for LinkedIn jobs using JSearch API"""
    
    def __init__(self):
        self.api_key = os.environ.get("JSEARCH_API_KEY")
        if not self.api_key:
            logger.warning("JSearch API key not found. Set the JSEARCH_API_KEY environment variable.")
    
    async def search(self, params: JobSearchRequest, limit: int = 5) -> List[JobResult]:
        logger.info(f"Searching LinkedIn jobs via JSearch API (limit: {limit})")
        
        if not self.api_key:
            logger.error("JSearch API key not available. Cannot search for LinkedIn jobs.")
            return []
            
        try:
            # Build search query
            query = params.position
            location = params.location if params.location else ""
            
            # Process experience requirements
            experience_code, years = map_experience_to_requirements(params.experience)
            
            # Get estimated salary information first - use rate limiter
            estimated_salary = None
            if query and location:
                estimated_salary = await get_estimated_salary(query, location, experience_code)
            
            # Extract salary range from params if available
            min_salary_param = None
            max_salary_param = None
            
            if params.salary:
                salary_match = re.search(r'\$?(\d+(?:,\d+)?)\s*-\s*\$?(\d+(?:,\d+)?)', params.salary)
                if salary_match:
                    min_salary_param = int(salary_match.group(1).replace(',', ''))
                    max_salary_param = int(salary_match.group(2).replace(',', ''))
            
            url = "https://jsearch.p.rapidapi.com/search"
            querystring = {
                "query": f"{query} in {location}" if location else query,
                "page": "1",
                "num_pages": "1",
                "site": "linkedin.com",  # Specify LinkedIn as the source
                "country": "us"
            }
            
            # Add salary parameter if available
            if min_salary_param:
                querystring["min_salary"] = min_salary_param
            if max_salary_param:
                querystring["max_salary"] = max_salary_param
            
            # Add job type filter if available
            if params.jobNature:
                job_type_map = {
                    "remote": "remote",
                    "onsite":"onsite"
                }
                job_type = job_type_map.get(params.jobNature.lower())
                if params.jobNature and params.jobNature.lower() == "remote":
                    querystring["remote_jobs_only"] = "true"  
                    querystring["work_from_home"] = "true"
                
            if experience_code:
                querystring["years_of_experience"] = experience_code
            
            headers = {
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": "jsearch.p.rapidapi.com"
            }
            
            async def make_linkedin_request():
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, params=querystring, timeout=30.0)
                    
                    if response.status_code != 200:
                        logger.error(f"JSearch API returned status code {response.status_code} for LinkedIn jobs")
                        if response.status_code == 429:
                            raise httpx.HTTPStatusError(f"Rate limit exceeded: {response.status_code}", request=response.request, response=response)
                        return []
                    
                    return response.json()
            
            # Use the rate limiter for the API call
            data = await rate_limiter.execute_with_retry("jsearch", make_linkedin_request)
            
            results = []
            if "data" in data:
                    for job in data["data"]:
                        try:
                            # Only include if the apply_link contains linkedin.com
                            apply_link = job.get("job_apply_link", "") or job.get("job_google_link", "")
                            
                            # Check if the job is actually from LinkedIn
                            if "linkedin.com" in apply_link:
                                # Extract any salary information from job posting if available
                                salary_info = None
                                experience_info = None
                                
                                # Process experience information
                                if estimated_salary:
                                    experience_code = estimated_salary.get("years_of_experience")
                                    experience_info = format_experience(experience_code) if experience_code else ""
                                    
                                    # Process salary information
                                    if min_salary_param and max_salary_param:
                                        median_salary = estimated_salary.get("median_salary")
                                        if median_salary and min_salary_param <= median_salary <= max_salary_param:
                                            salary_currency = estimated_salary.get("salary_currency", "USD")  # Get currency from estimated_salary
                                            if salary_currency == "PKR":
                                                salary_info = f"{median_salary:,.2f} PKR"
                                            else:
                                                salary_info = f"${median_salary:,.2f}"
                                            
                                # Process job nature (remote/onsite)
                                # First check if we requested remote jobs
                                if params.jobNature and params.jobNature.lower() == "remote":
                                    job_nature = "remote"
                                else:
                                    # Otherwise, check the job data
                                    is_remote = job.get("job_is_remote", False)
                                    work_from_home = job.get("work_from_home", False)
                                    
                                    # Convert string values to boolean if needed
                                    if isinstance(is_remote, str):
                                        is_remote = is_remote.lower() == "true"
                                    if isinstance(work_from_home, str):
                                        work_from_home = work_from_home.lower() == "true"
                                    
                                    job_nature = "remote" if (is_remote or work_from_home) else "onsite"
                                
                                # Look for remote keywords in job title or description
                                job_title = job.get("job_title", "").lower()
                                job_description = job.get("job_description", "").lower()
                                
                                if params.jobNature and params.jobNature.lower() == "remote":
                                    # If user requested remote jobs, force it to be remote
                                    job_nature = "remote"
                                elif "remote" in job_title or "work from home" in job_title or "remote" in job_description[:500]:
                                    job_nature = "remote"
                                
                                # Build location string
                                location_parts = []
                                if job.get("job_city"):
                                    location_parts.append(job.get("job_city"))
                                if job.get("job_state"):
                                    location_parts.append(job.get("job_state"))
                                if not location_parts and job.get("job_country"):
                                    location_parts.append(job.get("job_country"))
                                
                                job_data = JobResult(
                                    job_title=job.get("job_title", ""),
                                    company=job.get("employer_name", ""),
                                    experience=experience_info or "",
                                    location=", ".join(location_parts) if location_parts else "",
                                    salary=salary_info,
                                    jobNature=job_nature,
                                    apply_link=apply_link,
                                )
                                
                                # Only add jobs that match the requested job nature
                                if not params.jobNature or job_nature.lower() == params.jobNature.lower():
                                    results.append(job_data)
                                    
                        except Exception as e:
                            logger.error(f"Error parsing Indeed API job: {e}")
                
                   # logger.info(f"Found {len(results)} matching jobs via JSearch API for LinkedIn")
                    return results[:limit]
                
        except Exception as e:
            logger.error(f"Error searching LinkedIn via API: {str(e)}")
            return []
        
class LinkedInFallbackScraper:
    """Fallback scraper for LinkedIn jobs using web scraping (used if API key not available)"""
    
    async def search(self, params: JobSearchRequest, limit: int = 5) -> List[JobResult]:
        logger.info(f"Searching LinkedIn jobs via web scraping (limit: {limit})")
        try:
            # Build search query
            query_parts = [params.position]
            if params.location:
                query_parts.append(params.location)
            
            query = " ".join(query_parts)
            encoded_query = quote_plus(query)
            
            url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}"
            
            # Add filters if available
            if params.jobNature and params.jobNature.lower() == "remote":
                url += "&f_WT=2"
            
            async with httpx.AsyncClient(follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code != 200:
                    logger.error(f"LinkedIn returned status code {response.status_code}")
                    return []
                
                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.select("div.base-card")
                
                results = []
                for job in job_cards[:limit]:  # Limit the number of results
                    try:
                        title_elem = job.select_one(".base-search-card__title")
                        company_elem = job.select_one(".base-search-card__subtitle")
                        location_elem = job.select_one(".job-search-card__location")
                        link_elem = job.select_one("a.base-card__full-link")
                        
                        if title_elem and company_elem and link_elem:
                            job_data = JobResult(
                                job_title=title_elem.text.strip(),
                                company=company_elem.text.strip(),
                                location=location_elem.text.strip() if location_elem else None,
                                apply_link=link_elem["href"],
                                experience= "",
                                jobNature="",
                                salary=""
                            )
                            results.append(job_data)
                    except Exception as e:
                        logger.error(f"Error parsing LinkedIn job: {e}")
                
              #  logger.info(f"Found {len(results)} jobs on LinkedIn")
                return results
                
        except Exception as e:
            logger.error(f"Error searching LinkedIn: {str(e)}")
            return []