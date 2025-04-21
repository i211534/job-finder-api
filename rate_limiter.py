import asyncio
import time
import random
import logging
from typing import Dict, Any, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    An optimized rate limiter that minimizes delays while still respecting API limits.
    Uses a token bucket approach for more efficient rate limiting.
    """
    
    def __init__(self):
        # Track available tokens for each API
        self.tokens: Dict[str, float] = {}
        # Track last refill time
        self.last_refill: Dict[str, float] = {}
        
        # Define rate limits (requests per minute)
        self.rate_limits = {
            "jsearch": 5,      # 5 requests per minute for JSearch API
            "jobs_api": 5,     # 5 requests per minute for Jobs API
            "huggingface": 10, # 10 requests per minute for Hugging Face
            "default": 30      # Default limit for unspecified APIs
        }
        
        # Initialize token buckets for each API
        for api, limit in self.rate_limits.items():
            self.tokens[api] = limit
            self.last_refill[api] = time.time()
    
    def _refill_tokens(self, api_name: str) -> None:
        """Refill tokens based on time elapsed since last refill"""
        now = time.time()
        api = api_name if api_name in self.rate_limits else "default"
        
        # Get time elapsed since last refill
        elapsed = now - self.last_refill.get(api, now)
        
        # Calculate new tokens to add (tokens accrue at rate of limit per minute)
        rate = self.rate_limits[api] / 60.0  # tokens per second
        new_tokens = elapsed * rate
        
        # Update token count (never exceed the maximum)
        self.tokens[api] = min(self.tokens.get(api, 0) + new_tokens, self.rate_limits[api])
        self.last_refill[api] = now
    
    async def wait_for_rate_limit(self, api_name: str) -> float:
        """
        Wait only if necessary to respect rate limits.
        Returns the actual delay applied.
        """
        api = api_name if api_name in self.rate_limits else "default"
        
        # Refill tokens based on elapsed time
        self._refill_tokens(api)
        
        # If we have tokens available, use one immediately
        if self.tokens.get(api, 0) >= 1:
            self.tokens[api] -= 1
            return 0
        
        # Calculate minimum delay needed to get a token
        tokens_needed = 1
        rate = self.rate_limits[api] / 60.0  # tokens per second
        delay = tokens_needed / rate
        
        # Apply minimal jitter only when we're close to the limit
        jitter = random.uniform(0, 0.1)  # Add up to 100ms of jitter
        
        # Log only if the delay is significant
        if delay > 0.1:
            logger.info(f"Rate limiting {api_name}: Waiting {delay:.2f}s before next request")
        
        # Wait for the calculated time
        await asyncio.sleep(delay + jitter)
        
        # Consume the token we waited for
        self._refill_tokens(api)
        self.tokens[api] -= 1
        
        return delay + jitter
    
    async def execute_with_retry(
        self, 
        api_name: str,
        func: Callable[..., Awaitable[Any]], 
        *args, 
        max_retries: int = 3, 
        retry_status_codes: Optional[list] = None,
        **kwargs
    ) -> Any:
        """Execute a function with efficient retry logic"""
        if retry_status_codes is None:
            retry_status_codes = [429, 500, 502, 503, 504]
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Wait only if necessary before making the request
                await self.wait_for_rate_limit(api_name)
                
                # Call the function
                return await func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Check if it's a retriable error
                is_rate_limit = False
                status_code = None
                
                if hasattr(e, "status_code"):
                    status_code = e.status_code
                elif hasattr(e, "response") and hasattr(e.response, "status_code"):
                    status_code = e.response.status_code
                
                if status_code == 429:
                    is_rate_limit = True
                
                # Don't retry if it's not a retriable error and not a rate limit
                if status_code and status_code not in retry_status_codes and not is_rate_limit:
                    raise
                
                # Use adaptive backoff that's faster for earlier retries
                # and provides just enough delay for rate limits
                if is_rate_limit:
                    # For rate limit errors, use Retry-After header or default to progressive backoff
                    retry_after = None
                    if hasattr(e, "response") and hasattr(e.response, "headers"):
                        retry_after = e.response.headers.get("Retry-After")
                    
                    if retry_after and retry_after.isdigit():
                        delay = float(retry_after) + 0.1  # Slight buffer
                    else:
                        # Progressive backoff for rate limits
                        delay = min(2 * (attempt + 1), 30)  # Cap at 30 seconds
                else:
                    # Short delays for other errors
                    delay = 0.5 * (attempt + 1)  # 0.5s, 1.0s, 1.5s
                
                # Last attempt, don't wait
                if attempt == max_retries - 1:
                    raise
                
                if delay > 0.5:
                    logger.info(f"{api_name} error (attempt {attempt+1}/{max_retries}): Retrying in {delay:.1f}s")
                
                await asyncio.sleep(delay)
        
        # This should never be reached due to the raise in the loop
        raise last_exception if last_exception else RuntimeError("Unknown error in execute_with_retry")