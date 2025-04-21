# Helper function to convert API experience format to user-friendly format
import logging
import os
import re
import httpx
from typing import Tuple, Optional
from rate_limiter import RateLimiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rate_limiter = RateLimiter()

def format_experience(experience_code):
    """Convert API experience code to user-friendly format"""
    if not experience_code or experience_code == "ALL":
        return "Any experience"
    
    experience_map = {
        "LESS_THAN_ONE": "Less than 1 year",
        "ONE_TO_THREE": "1-3 years",
        "FOUR_TO_SIX": "4-6 years",
        "SEVEN_TO_NINE": "7-9 years", 
        "TEN_TO_FOURTEEN": "10-14 years",
        "ABOVE_FIFTEEN": "15+ years"
    }
    
    return experience_map.get(experience_code, experience_code)

def map_experience_to_requirements(experience_str):
    """Convert experience string to API requirements format and extract years"""
    if not experience_str:
        return "ALL", None
        
    # Extract numbers from the experience string
    years_match = re.search(r'(\d+)', experience_str)
    years = int(years_match.group(1)) if years_match else None
    
    # Handle various formats and convert to API parameters
    if years is not None:
        if years < 1:
            return "LESS_THAN_ONE", years
        elif 1 <= years <= 3:
            return "ONE_TO_THREE", years
        elif 4 <= years <= 6:
            return "FOUR_TO_SIX", years
        elif 7 <= years <= 9:
            return "SEVEN_TO_NINE", years
        elif 10 <= years <= 14:
            return "TEN_TO_FOURTEEN", years
        elif years >= 15:
            return "ABOVE_FIFTEEN", years
    
    # Handle text-based descriptions
    lower_exp = experience_str.lower()
    if "no experience" in lower_exp or "0 years" in lower_exp:
        return "LESS_THAN_ONE", 0
    elif "entry" in lower_exp or "junior" in lower_exp:
        return "LESS_THAN_ONE", 0
    elif "mid" in lower_exp:
        return "FOUR_TO_SIX", 5
    elif "senior" in lower_exp or "experienced" in lower_exp:
        return "SEVEN_TO_NINE", 8
    elif "expert" in lower_exp or "principal" in lower_exp:
        return "TEN_TO_FOURTEEN", 12
    
    # Default to ALL if no clear mapping
    return "ALL", None

async def get_estimated_salary(job_title, location, years_experience):
    """Get estimated salary for a job title in a location with specified experience"""
    api_key = os.environ.get("JSEARCH_API_KEY")
    if not api_key:
        logger.warning("JSearch API key not found. Cannot get estimated salary.")
        return None
        
    try:
        url = "https://jsearch.p.rapidapi.com/estimated-salary"
        querystring = {
            "job_title": job_title,
            "location": location,
            "location_type": "ANY",
            "years_of_experience": years_experience or "ALL"
        }
        
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "jsearch.p.rapidapi.com"
        }
        
        async def make_request():
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=querystring, timeout=30.0)
                
                if response.status_code != 200:
                    logger.error(f"Estimated salary API returned status code {response.status_code}")
                    if response.status_code == 429:
                        raise httpx.HTTPStatusError(f"Rate limit exceeded: {response.status_code}", request=response.request, response=response)
                    return None
                
                data = response.json()
                # Extract and return the salary information
                if "data" in data and data["data"]:
                    salary_data = data["data"][0]
                    return {
                        "min_salary": salary_data.get("min_salary"),
                        "max_salary": salary_data.get("max_salary"),
                        "median_salary": salary_data.get("median_salary"),
                        "years_of_experience": years_experience,
                        "salary_currency": salary_data.get("salary_currency", "USD")
                    }
                return None
        
        # Use the rate limiter for the API call
        return await rate_limiter.execute_with_retry("jsearch", make_request)
            
    except Exception as e:
        logger.error(f"Error getting estimated salary: {str(e)}")
        return None
    
def parse_salary_range(salary_string: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Parse a salary string like "55,020.16–64,729.60 a year" into min, max, and period.
    Returns a tuple of (min_salary, max_salary, period).
    """
    if not salary_string:
        return None, None, None
    
    # Handle various salary formats
    # Format: "55,020.16–64,729.60 a year" or "$55,020.16 - $64,729.60 per year"
    pattern = r'[$]?([0-9,\.]+)[\s]*[-–][\s]*[$]?([0-9,\.]+)[\s]*(per|a|an|\/)?[\s]*(year|month|hour|yr|wk|week|day|annual)?'
    match = re.search(pattern, salary_string)
    
    if match:
        # Extract the min and max salaries
        min_salary = float(match.group(1).replace(',', ''))
        max_salary = float(match.group(2).replace(',', ''))
        
        # Extract the period (year, month, hour, etc.)
        period = match.group(4) if match.group(4) else None
        
        return min_salary, max_salary, period
    else:
        # Format: "$55,020.16 a year" or "55,020.16 per year"
        pattern = r'[$]?([0-9,\.]+)[\s]*(per|a|an|\/)?[\s]*(year|month|hour|yr|wk|week|day|annual)?'
        match = re.search(pattern, salary_string)
        
        if match:
            salary = float(match.group(1).replace(',', ''))
            period = match.group(3) if match.group(3) else None
            return salary, salary, period
    
    return None, None, None

def normalize_annual_salary(salary: float, period: str) -> float:
    """
    Convert salary to annual equivalent based on the period.
    """
    if not period:
        return salary
    
    period = period.lower()
    if 'hour' in period:
        return salary * 40 * 52  # 40 hours/week, 52 weeks/year
    elif 'day' in period:
        return salary * 5 * 52  # 5 days/week, 52 weeks/year
    elif 'week' in period or 'wk' in period:
        return salary * 52  # 52 weeks/year
    elif 'month' in period:
        return salary * 12  # 12 months/year
    else:  # 'year', 'annual', 'yr'
        return salary

def is_salary_in_range(job_salary: str, user_min: float, user_max: float) -> bool:
    """
    Check if the job salary is within the user's specified range.
    Returns True if within range, False if outside range or couldn't be parsed.
    """
    if not job_salary:
        return False
    
    # Parse the job salary
    job_min, job_max, period = parse_salary_range(job_salary)
    if job_min is None:
        return False
    
    # Normalize to annual salary if period is specified
    if period:
        job_min = normalize_annual_salary(job_min, period)
        job_max = normalize_annual_salary(job_max, period)
    
    # Check if there's overlap between ranges
    # A job is considered a match if any part of its salary range overlaps with the user's range
    return not (job_max < user_min or job_min > user_max)