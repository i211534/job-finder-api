#indeed_scraper.py

from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import httpx
import logging
import os
from typing import List
from models import JobResult, JobSearchRequest
import re
from rate_limiter import RateLimiter

rate_limiter = RateLimiter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IndeedAPIScraper:
    """API-based scraper for Indeed jobs using JSearch API"""
    
    def __init__(self):
        self.api_key = os.environ.get("JSEARCH_API_KEY")
        if not self.api_key:
            logger.warning("JSearch API key not found. Set the JSEARCH_API_KEY environment variable.")
    
    async def search(self, params: JobSearchRequest, limit: int = 5) -> List[JobResult]:
        logger.info(f"Searching Indeed jobs via JSearch API (limit: {limit})")
        
        if not self.api_key:
            logger.error("JSearch API key not available. Cannot search for jobs.")
            return []
            
        try:
            # Build search query
            query = params.position
            location = params.location if params.location else ""
            from functions import map_experience_to_requirements
            # Process experience requirements
            experience_code, years = map_experience_to_requirements(params.experience)
            from functions import get_estimated_salary
            # Get estimated salary information first
            estimated_salary = None
            if query and location:
                estimated_salary = await get_estimated_salary(query, location, experience_code)
            
            # Extract salary range from params if available
            min_salary_param = None
            max_salary_param = None
            
            if params.salary:
                # Extract min and max salary from string like "$3000 - $5000"
                salary_match = re.search(r'\$?(\d+(?:,\d+)?)\s*-\s*\$?(\d+(?:,\d+)?)', params.salary)
                if salary_match:
                    min_salary_param = int(salary_match.group(1).replace(',', ''))
                    max_salary_param = int(salary_match.group(2).replace(',', ''))
            
            # Build the job search query
            url = "https://jsearch.p.rapidapi.com/search"
            querystring = {
                "query": f"{query} in {location}" if location else query,
                "page": "1",
                "num_pages": "1",
                "site": "indeed.com",  
                "country": "us"
            }
            
            if min_salary_param:
                querystring["min_salary"] = min_salary_param
            if max_salary_param:
                querystring["max_salary"] = max_salary_param
            
            if params.jobNature:
                job_nature_lowercase = params.jobNature.lower()
                if job_nature_lowercase == "remote":
                    # Set multiple parameters to ensure we get remote jobs
                    querystring["work_from_home"] = "true"
                    querystring["remote_jobs_only"] = "true"
                    # Add "remote" to the search query for better results
                    querystring["query"] = f"{querystring['query']} remote"
                elif job_nature_lowercase == "onsite":
                    querystring["work_from_home"] = "false"
                
            if experience_code:
                querystring["years_of_experience"] = experience_code

            headers = {
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": "jsearch.p.rapidapi.com"
            }
            
            #logger.info(f"JSearch API querystring: {querystring}")  
            
            async def make_indeed_request():
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, params=querystring, timeout=30.0)
                    
                    if response.status_code != 200:
                        logger.error(f"JSearch API returned status code {response.status_code}")
                        if response.status_code == 429:
                            raise httpx.HTTPStatusError(f"Rate limit exceeded: {response.status_code}", request=response.request, response=response)
                        return []
                    
                    return response.json()
            
            # Use the rate limiter for the API call
            data = await rate_limiter.execute_with_retry("jsearch", make_indeed_request)
            
            # if "data" in data:
            #     logger.info(f"JSearch API returned {len(data['data'])} results")
            
            results = []
            from functions import format_experience
            if "data" in data:
                for job in data["data"]:
                    try:
                        # Only include if the apply_link contains indeed.com
                        apply_link = job.get("job_apply_link", "") or job.get("job_google_link", "")
                        
                        # Check if the job is actually from Indeed
                        if "indeed.com" in apply_link:
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
            
            #logger.info(f"Found {len(results)} matching jobs via JSearch API for Indeed")
            return results[:limit]  # Ensure we don't exceed the requested limit
            
        except Exception as e:
            logger.error(f"Error searching Indeed API: {str(e)}")
            return []
        
class IndeedFallbackScraper:
    """Fallback scraper for Indeed jobs using web scraping (used if API key not available)"""
    
    async def search(self, params: JobSearchRequest, limit: int = 5) -> List[JobResult]:
        logger.info(f"Searching Indeed jobs via web scraping (limit: {limit})")
        try:
            # Build search query
            query = params.position
            location = params.location if params.location else ""
            
            # Encode the query parameters
            encoded_query = quote_plus(query)
            encoded_location = quote_plus(location)
            
            url = f"https://www.indeed.com/jobs?q={encoded_query}&l={encoded_location}"
            
            # Add job type filter if available
            if params.jobNature:
                job_type_map = {
                    "full-time": "fulltime",
                    "part-time": "parttime",
                    "contract": "contract",
                    "temporary": "temporary",
                    "internship": "internship"
                }
                job_type = job_type_map.get(params.jobNature.lower())
                if job_type:
                    url += f"&jt={job_type}"
            
            async with httpx.AsyncClient(follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code != 200:
                    logger.error(f"Indeed returned status code {response.status_code}")
                    return []
                
                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.select("div.job_seen_beacon")
                
                results = []
                for job in job_cards[:limit]:  # Limit the number of results
                    try:
                        title_elem = job.select_one("h2.jobTitle span[title]") or job.select_one("h2.jobTitle")
                        company_elem = job.select_one("span.companyName")
                        location_elem = job.select_one("div.companyLocation")
                        
                        # Get job link
                        link = None
                        job_id_elem = job.get("data-jk")
                        if job_id_elem:
                            link = f"https://www.indeed.com/viewjob?jk={job_id_elem}"
                        
                        # Get salary if available
                        salary_elem = job.select_one("div.metadata.salary-snippet-container")
                        salary = salary_elem.text.strip() if salary_elem else None
                        
                        # Get job type if available
                        job_type_elem = job.select_one("div.attribute_snippet")
                        job_type = job_type_elem.text.strip() if job_type_elem else None
                        
                        if title_elem and company_elem:
                            job_data = JobResult(
                                job_title=title_elem.text.strip(),
                                company=company_elem.text.strip(),
                                location=location_elem.text.strip() if location_elem else None,
                                salary=salary,
                                jobNature=job_type,
                                apply_link=link if link else "https://www.indeed.com/",
                                job_id=job_id_elem if job_id_elem else None,
                                source="Indeed"
                            )
                            results.append(job_data)
                    except Exception as e:
                        logger.error(f"Error parsing Indeed job: {e}")
                
               # logger.info(f"Found {len(results)} jobs on Indeed")
                return results
                
        except Exception as e:
            logger.error(f"Error searching Indeed: {str(e)}")
            return []