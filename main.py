#main.py
from fastapi import FastAPI, HTTPException, Query
import logging
from dotenv import load_dotenv
from class_filter import JobRelevanceFilter
from formatter_integration import prepare_final_output
from indeed_scraper import IndeedAPIScraper, IndeedFallbackScraper
from linedin_scrappers import LinkedInAPIScraper, LinkedInFallbackScraper
from models import JobSearchRequest
from rate_limiter import RateLimiter

load_dotenv()
rate_limiter = RateLimiter()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Job Search API", description="API for searching jobs across multiple platforms")

@app.post("/find-jobs")
async def find_jobs(request: JobSearchRequest, limit: int = Query(default=3, ge=1, le=5)):
    """
    Find jobs based on search criteria and return results in standardized format
    """
    try:

        linkedin_api_scraper = LinkedInAPIScraper()
        indeed_scraper = IndeedAPIScraper()
       # indeed_fallback_scraper = IndeedFallbackScraper()
        linkedin_fallback_scraper = LinkedInFallbackScraper()
        
        from googlejobs_scraper import GoogleJobsAPIScraper
        google_jobs_scraper = GoogleJobsAPIScraper()
        
        #logger.info("Using JSearch API for LinkedIn and Indeed, and Jobs API for Google Jobs")
        
        scraper_limit = 5
        
        linkedin_api_results = await linkedin_api_scraper.search(request, limit=scraper_limit)
        
        if not linkedin_api_results:
            logger.info("No jobs found from LinkedIn API, using fallback scraper")
            linkedin_fallback_results = await linkedin_fallback_scraper.search(request, limit=scraper_limit)
            linkedin_results = linkedin_fallback_results
        else:
            linkedin_results = linkedin_api_results
        
        indeed_api_results = await indeed_scraper.search(request, limit=scraper_limit)
        
        google_jobs_results = []
        if google_jobs_scraper:
            google_jobs_results = await google_jobs_scraper.search(request, limit=scraper_limit)
        
        all_jobs = linkedin_results + indeed_api_results + google_jobs_results
        
        if not all_jobs:
            return {"relevant_jobs": []}
        
        relevance_filter = JobRelevanceFilter()
        
        jobs_with_descriptions = await relevance_filter.fetch_job_descriptions(all_jobs)
        
        scored_jobs = await relevance_filter.score_jobs(jobs_with_descriptions, request)
        
        formatted_output = prepare_final_output(scored_jobs)
        
        return formatted_output
        
    except Exception as e:
        logger.error(f"Error in enhanced_find_jobs endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)