#class_filter.py
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup
import asyncio
import re
import logging
import os
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import json
import time
import random
from models import JobResult, JobSearchRequest
from rate_limiter import RateLimiter

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobRelevanceFilter:
    def __init__(self):
        api_key = os.environ.get("HUGGINGFACE_API_KEY")
        if not api_key:
            raise ValueError("Hugging Face API key not found. Set the HUGGINGFACE_API_KEY environment variable.")
        self.client = InferenceClient(token=api_key)
        
        self.jsearch_api_key = os.environ.get("JSEARCH_API_KEY")
        if not self.jsearch_api_key:
            logger.warning("JSearch API key not found. Set the JSEARCH_API_KEY environment variable for API integration.")
        
        self.score_cache = {}  
        self.last_api_call = 0  
        self.min_delay = 1.0  
        
        self.rate_limiter = RateLimiter()

    async def fetch_job_descriptions(self, jobs: List[JobResult]) -> List[JobResult]:
        jobs_with_descriptions = []
        MAX_DESCRIPTION_FETCHES = 6
        description_count = 0
        
        for job in jobs:
            if job.description:
                jobs_with_descriptions.append(job)
                continue
            
            if description_count >= MAX_DESCRIPTION_FETCHES:
                job.description = f"{job.job_title} at {job.company}"
                jobs_with_descriptions.append(job)
                continue
                
            try:
                if job.job_id and self.jsearch_api_key:
                    description = await self._fetch_jsearch_api_description(job.job_id)
                    job.description = description
                    description_count += 1
                elif job.source == "LinkedIn" and job.apply_link:
                    description = await self._fetch_linkedin_description(job.apply_link)
                    job.description = description
                    description_count += 1
                elif job.source == "Indeed" and job.apply_link:
                    description = await self._fetch_indeed_description(job.apply_link)
                    job.description = description
                    description_count += 1
                
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                logger.error(f"Error fetching description for {job.job_title}: {str(e)}")
                job.description = f"{job.job_title} at {job.company}"
                
            jobs_with_descriptions.append(job)
            
        return jobs_with_descriptions
    
    async def _fetch_linkedin_description(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code != 200:
                    return ""
                    
                soup = BeautifulSoup(response.text, "html.parser")
                description_div = soup.select_one("div.description__text")
                
                if description_div:
                    return description_div.text.strip()
                return ""
        except Exception as e:
            logger.error(f"Error fetching LinkedIn description: {str(e)}")
            return ""
    def extract_skills_from_description(self, description: str, user_skills: List[str]) -> Dict[str, float]:
        if not description or not user_skills:
            return {}
        
        matched_skills = {}
        description_lower = description.lower()
        
        for skill in user_skills:
            skill_lower = skill.lower().strip()
            if not skill_lower:
                continue
                
            if skill_lower in description_lower:
                matched_skills[skill] = 1.0
                continue
                
            words = skill_lower.split()
            if len(words) > 1:
                matched_words = sum(1 for word in words if word in description_lower)
                if matched_words > 0:
                    confidence = matched_words / len(words)
                    if confidence > 0.5:
                        matched_skills[skill] = confidence
        
        return matched_skills
    async def _fetch_jsearch_api_description(self, job_id: str) -> str:
        if not self.jsearch_api_key:
            logger.warning("JSearch API key not available. Cannot fetch job details from API.")
            return ""
            
        try:
            url = "https://jsearch.p.rapidapi.com/job-details"
            querystring = {"job_id": job_id, "country": "us"}
            headers = {
                "x-rapidapi-key": self.jsearch_api_key,
                "x-rapidapi-host": "jsearch.p.rapidapi.com"
            }
            
            async def make_jsearch_request():
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, params=querystring, timeout=30.0)
                    
                    if response.status_code != 200:
                        logger.error(f"JSearch API returned status code {response.status_code}")
                        if response.status_code == 429:
                            raise httpx.HTTPStatusError(f"Rate limit exceeded: {response.status_code}", request=response.request, response=response)
                        return ""
                    
                    data = response.json()
                    
                    if "data" in data and data["data"]:
                        job_data = data["data"][0]
                        description = job_data.get("job_description", "")
                        return description
                    
                    return ""
            
            return await self.rate_limiter.execute_with_retry("jsearch", make_jsearch_request)
                
        except Exception as e:
            logger.error(f"Error fetching job details from JSearch API: {str(e)}")
            return ""
    
    async def _fetch_indeed_description(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code != 200:
                    return ""
                    
                soup = BeautifulSoup(response.text, "html.parser")
                description_div = soup.select_one("div#jobDescriptionText")
                
                if description_div:
                    return description_div.text.strip()
                return ""
        except Exception as e:
            logger.error(f"Error fetching Indeed description: {str(e)}")
            return ""    

    async def score_jobs(self, jobs: List[JobResult], criteria: JobSearchRequest) -> List[JobResult]:
        if not jobs:
            return []
        
        user_skills = []
        if criteria.skills:
            user_skills = [skill.strip() for skill in criteria.skills.lower().split(',')]
        
        prioritized_jobs = self._prefilter_jobs(jobs, criteria)
        
        MAX_JOBS_TO_SCORE = 6
        jobs_to_score = prioritized_jobs[:MAX_JOBS_TO_SCORE]
        remaining_jobs = prioritized_jobs[MAX_JOBS_TO_SCORE:]
        
        scored_jobs = []
        for job in jobs_to_score:
            try:
                cache_key = f"{job.job_title}_{job.company}_{criteria.position}"
                
                if cache_key in self.score_cache:
                    job.relevance_score = self.score_cache[cache_key]
                else:
                    await self._respect_rate_limit()
                    
                    prompt = self._create_scoring_prompt(job, criteria)
                    base_score = await self._get_job_score(prompt)
                    
                    skills_boost = 0.0
                    if user_skills and job.description:
                        matched_skills = self.extract_skills_from_description(job.description, user_skills)
                        
                        if matched_skills and user_skills:
                            match_percentage = len(matched_skills) / len(user_skills)
                            skills_boost = min(0.3, match_percentage * 0.3)
                            
                            #job.matched_skills = matched_skills
                    
                    #job.relevance_score = min(1.0, base_score + skills_boost)
                    self.score_cache[cache_key] = job.relevance_score
                
                scored_jobs.append(job)
                    
            except Exception as e:
                logger.error(f"Error scoring job {job.job_title}: {str(e)}")
                job.relevance_score = 0
                scored_jobs.append(job)
        
        for job in remaining_jobs:
            base_score = 0.3
            
            skills_boost = 0.0
            if user_skills and job.description:
                matched_skills = self.extract_skills_from_description(job.description, user_skills)
                if matched_skills and user_skills:
                    match_percentage = len(matched_skills) / len(user_skills)
                    skills_boost = min(0.2, match_percentage * 0.2)
                    #job.matched_skills = matched_skills
            
            #job.relevance_score = min(0.5, base_score + skills_boost)
            scored_jobs.append(job)
        
        return sorted(scored_jobs, key=lambda x: x.relevance_score if x.relevance_score is not None else 0, reverse=True)
    
    def _prefilter_jobs(self, jobs: List[JobResult], criteria: JobSearchRequest) -> List[JobResult]:
        job_scores = []
        
        user_skills = []
        if criteria.skills:
            user_skills = [skill.strip() for skill in criteria.skills.lower().split(',')]
        
        for job in jobs:
            score = 0
            if criteria.position.lower() in job.job_title.lower():
                score += 5
            
            if user_skills and job.description:
                description_lower = job.description.lower()
                skills_found = 0
                
                for skill in user_skills:
                    skill_lower = skill.lower()
                    if skill_lower in description_lower:
                        skills_found += 1
                        
                        if skill_lower in job.job_title.lower():
                            score += 2
                        else:
                            score += 1
                
                if skills_found > len(user_skills) / 2:
                    score += 2
            
            if criteria.location and job.location:
                if criteria.location.lower() in job.location.lower():
                    score += 2
            
            job_scores.append((job, score))
        
        return [job for job, _ in sorted(job_scores, key=lambda x: x[1], reverse=True)]
    
    async def _process_job_batch(self, jobs: List[JobResult], criteria: JobSearchRequest) -> List[JobResult]:
        scored_jobs = []
        
        for job in jobs:
            cache_key = f"{job.job_title}_{job.company}_{criteria.position}"
            if cache_key in self.score_cache:
                job.relevance_score = self.score_cache[cache_key]
                scored_jobs.append(job)
                continue
            
            try:
                await self._respect_rate_limit()
                
                prompt = self._create_scoring_prompt(job, criteria)
                score = await self._get_job_score(prompt)
                
                job.relevance_score = score
                self.score_cache[cache_key] = score
                scored_jobs.append(job)
                
            except Exception as e:
                logger.error(f"Error scoring job {job.job_title}: {str(e)}")
                job.relevance_score = 0
                scored_jobs.append(job)
                
        return scored_jobs
    
    async def _respect_rate_limit(self):
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        
        if time_since_last_call < self.min_delay:
            delay = self.min_delay - time_since_last_call + random.uniform(0.1, 0.5)
            logger.info(f"Rate limiting: Waiting {delay:.2f} seconds before next API call")
            await asyncio.sleep(delay)
        
        self.last_api_call = time.time()
    
    def _create_scoring_prompt(self, job: JobResult, criteria: JobSearchRequest) -> str:
        job_info = {
            "title": job.job_title,
            "company": job.company,
            "location": job.location if job.location else "Not specified",
            "job_type": job.jobNature if job.jobNature else "Not specified",
            "salary": job.salary if job.salary else "Not specified",
            "experience": job.experience if job.experience else "Not specified",
            "description": job.description if job.description else "Not available"
        }
        
        user_criteria = {
            "position": criteria.position,
            "location": criteria.location if criteria.location else "Not specified",
            "job_type": criteria.jobNature if criteria.jobNature else "Not specified",
            "salary": criteria.salary if criteria.salary else "Not specified",
            "experience": criteria.experience if criteria.experience else "Not specified",
            "skills": criteria.skills if criteria.skills else "Not specified"
        }
        
        description_preview = job_info["description"][:500] if job_info["description"] else "Not available"
        
        prompt = """
        Score job relevance (0.0-1.0):
        
        Job: {title} at {company}
        Location: {location}
        Type: {job_type}
        Salary: {salary}
        Experience: {experience}
        
        User wants:
        Position: {position}
        Location: {user_location}
        Type: {user_job_type}
        Salary: {user_salary}
        Experience: {user_experience}
        Skills: {user_skills}
        
        Job description excerpt: {description}...
        
        Pay special attention to skills match. If the required skills match the user's skills, give higher score.
        
        Return only: {{"score": 0.XX}}
        """.format(
            title=job_info["title"],
            company=job_info["company"],
            location=job_info["location"],
            job_type=job_info["job_type"],
            salary=job_info["salary"],
            experience=job_info["experience"],
            description=description_preview,
            position=user_criteria["position"],
            user_location=user_criteria["location"],
            user_job_type=user_criteria["job_type"],
            user_salary=user_criteria["salary"],
            user_experience=user_criteria["experience"],
            user_skills=user_criteria["skills"]
        )
        
        return prompt
    
    async def _get_job_score(self, prompt: str) -> float:
        try:
            response = await self._call_huggingface_api(prompt)

            try:
                result = json.loads(response)
                return float(result.get("score", 0.0))
            except (json.JSONDecodeError, AttributeError, TypeError):
                match = re.search(r"(\d+\.\d+)", response)
                if match:
                    return float(match.group(1))
                return 0.0
        except Exception as e:
            logger.error(f"Error getting job score: {str(e)}")
            return 0.0

    
    async def _call_huggingface_api(self, prompt: str) -> str:
        async def make_huggingface_request():
            return await asyncio.to_thread(
                self.client.text_generation,
                prompt,
                model="google/flan-t5-base",
                max_new_tokens=50,
                temperature=0.2
            )
        
        try:
            result = await self.rate_limiter.execute_with_retry(
                "huggingface", 
                make_huggingface_request
            )
            return result.strip()
        except Exception as e:
            logger.error(f"Error calling Hugging Face API after retries: {str(e)}")
            raise