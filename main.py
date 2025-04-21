#main.py
# Import necessary libraries and modules
from fastapi import FastAPI, HTTPException, Query  # FastAPI framework for building the API
import logging  # For logging information and errors
from dotenv import load_dotenv  # To load environment variables from .env file
from class_filter import JobRelevanceFilter  # Custom module for scoring job relevance
from formatter_integration import prepare_final_output  # Module to format the final output
# Import scrapers for different job platforms
from indeed_scraper import IndeedAPIScraper, IndeedFallbackScraper  
from linedin_scrappers import LinkedInAPIScraper, LinkedInFallbackScraper
from models import JobSearchRequest  # Data model for job search requests
from rate_limiter import RateLimiter  # Module to handle API rate limiting

# Load environment variables from .env file
load_dotenv()
# Initialize rate limiter to prevent API rate limit errors
rate_limiter = RateLimiter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(title="Job Search API", description="API for searching jobs across multiple platforms")

@app.post("/find-jobs")
async def find_jobs(request: JobSearchRequest, limit: int = Query(default=3, ge=1, le=5)):
    """
    Find jobs based on search criteria and return results in standardized format
    
    Parameters:
    - request: JobSearchRequest object containing search criteria (position, location, etc.)
    - limit: Maximum number of results to return (between 1 and 5, default is 3)
    
    Returns:
    - Dictionary containing relevant jobs formatted according to requirements
    """
    try:
        # Initialize scrapers for different job platforms
        linkedin_api_scraper = LinkedInAPIScraper()
        indeed_scraper = IndeedAPIScraper()
        # Initialize fallback scraper for LinkedIn (used if API fails)
        linkedin_fallback_scraper = LinkedInFallbackScraper()
        
        # Import and initialize Google Jobs scraper
        from googlejobs_scraper import GoogleJobsAPIScraper
        google_jobs_scraper = GoogleJobsAPIScraper()
        
        # Set number of results to fetch from each scraper
        # This is higher than the final limit to ensure enough jobs for filtering
        scraper_limit = 5
        
        # Get job results from LinkedIn API
        linkedin_api_results = await linkedin_api_scraper.search(request, limit=scraper_limit)
        
        # If LinkedIn API returns no results, use fallback scraper (web scraping)
        if not linkedin_api_results:
            logger.info("No jobs found from LinkedIn API, using fallback scraper")
            linkedin_fallback_results = await linkedin_fallback_scraper.search(request, limit=scraper_limit)
            linkedin_results = linkedin_fallback_results
        else:
            linkedin_results = linkedin_api_results
        
        # Get job results from Indeed API
        indeed_api_results = await indeed_scraper.search(request, limit=scraper_limit)
        
        # Initialize empty list for Google Jobs results
        google_jobs_results = []
        # If Google Jobs scraper is available, fetch results
        if google_jobs_scraper:
            google_jobs_results = await google_jobs_scraper.search(request, limit=scraper_limit)
        
        # Combine results from all sources
        all_jobs = linkedin_results + indeed_api_results + google_jobs_results
        
        # If no jobs found across all platforms, return empty list
        if not all_jobs:
            return {"relevant_jobs": []}
        
        # Initialize the JobRelevanceFilter to score and filter jobs
        relevance_filter = JobRelevanceFilter()
        
        # Fetch detailed job descriptions for better relevance scoring
        # This will selectively fetch descriptions for a subset of jobs to avoid rate limiting
        jobs_with_descriptions = await relevance_filter.fetch_job_descriptions(all_jobs)
        
        # Score the jobs based on relevance to user criteria
        # This uses a Hugging Face model to evaluate job relevance
        scored_jobs = await relevance_filter.score_jobs(jobs_with_descriptions, request)
        
        # Format the results according to the required output structure
        formatted_output = prepare_final_output(scored_jobs)
        
        # Return the formatted results
        return formatted_output
        
    except Exception as e:
        # Log any errors that occur during processing
        logger.error(f"Error in enhanced_find_jobs endpoint: {str(e)}")
        # Return a 500 error with error details
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# Entry point for running the application directly
if __name__ == "__main__":
    import uvicorn
    # Run the FastAPI application with uvicorn server
    # - host="0.0.0.0" makes it available on all network interfaces
    # - port=8000 is the standard port for FastAPI applications
    # - reload=True enables auto-reloading when code changes (for development)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)