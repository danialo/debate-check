"""
Base interface for fact-checking services
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import asyncio
import aiohttp
from ..fact_models import FactCheckResult, VerificationStatus

logger = logging.getLogger(__name__)


class FactCheckService(ABC):
    """Abstract base class for fact-checking services"""
    
    def __init__(self, name: str, timeout_seconds: int = 10):
        self.name = name
        self.timeout_seconds = timeout_seconds
        self.logger = logger.getChild(name)
    
    @abstractmethod
    async def verify_claim(self, claim_text: str, **kwargs) -> FactCheckResult:
        """
        Verify a single claim
        
        Args:
            claim_text: The claim text to verify
            **kwargs: Additional service-specific parameters
            
        Returns:
            FactCheckResult with verification data
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this service is available and properly configured
        
        Returns:
            True if service can be used, False otherwise
        """
        pass
    
    def preprocess_claim(self, claim_text: str) -> str:
        """
        Preprocess claim text for better API queries
        
        Args:
            claim_text: Raw claim text
            
        Returns:
            Processed claim text optimized for fact-checking APIs
        """
        # Remove extra whitespace
        processed = " ".join(claim_text.split())
        
        # Remove speaker attribution if present
        if ":" in processed and len(processed.split(":")[0]) < 50:
            processed = ":".join(processed.split(":")[1:]).strip()
        
        # Limit length for API efficiency
        if len(processed) > 500:
            processed = processed[:497] + "..."
        
        return processed
    
    def create_error_result(self, 
                           claim_text: str, 
                           error_message: str,
                           query: str = None) -> FactCheckResult:
        """
        Create a standardized error result
        
        Args:
            claim_text: Original claim text
            error_message: Error description
            query: Query that was sent (if any)
            
        Returns:
            FactCheckResult with error status
        """
        return FactCheckResult(
            service_name=self.name,
            query=query or claim_text,
            claim_text=claim_text,
            status=VerificationStatus.ERROR,
            confidence=0.0,
            verification_score=0.5,  # Neutral score for errors
            explanation=f"Error from {self.name}: {error_message}",
            sources=[]
        )


class HTTPFactCheckService(FactCheckService):
    """Base class for HTTP-based fact-checking services"""
    
    def __init__(self, 
                 name: str, 
                 base_url: str,
                 timeout_seconds: int = 10,
                 max_retries: int = 3):
        super().__init__(name, timeout_seconds)
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self):
        """Ensure HTTP session is initialized"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def _make_request(self, 
                           method: str, 
                           endpoint: str, 
                           **kwargs) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request with retries and error handling
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (will be appended to base_url)
            **kwargs: Additional arguments for aiohttp request
            
        Returns:
            JSON response data or None if failed
        """
        await self._ensure_session()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                
                start_time = time.time()
                
                async with self.session.request(method, url, **kwargs) as response:
                    processing_time = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        data = await response.json()
                        self.logger.debug(f"Request successful in {processing_time}ms")
                        return data
                    elif response.status == 429:  # Rate limited
                        wait_time = 2 ** attempt  # Exponential backoff
                        self.logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"HTTP {response.status}: {await response.text()}")
                        break
                        
            except asyncio.TimeoutError:
                self.logger.warning(f"Request timeout (attempt {attempt + 1})")
                if attempt == self.max_retries - 1:
                    self.logger.error("All retry attempts failed due to timeout")
                    
            except Exception as e:
                self.logger.error(f"Request failed: {e}")
                if attempt == self.max_retries - 1:
                    self.logger.error("All retry attempts failed")
                    
        return None
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


class RateLimitedService(HTTPFactCheckService):
    """Base class for services with rate limiting"""
    
    def __init__(self, 
                 name: str, 
                 base_url: str, 
                 requests_per_minute: int = 60,
                 **kwargs):
        super().__init__(name, base_url, **kwargs)
        self.requests_per_minute = requests_per_minute
        self.request_times: List[float] = []
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        current_time = time.time()
        
        # Remove requests older than 1 minute
        self.request_times = [
            req_time for req_time in self.request_times 
            if current_time - req_time < 60
        ]
        
        # If we're at the limit, wait
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (current_time - self.request_times[0])
            if wait_time > 0:
                self.logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
        
        # Record this request
        self.request_times.append(current_time)
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Override to add rate limiting"""
        await self._check_rate_limit()
        return await super()._make_request(method, endpoint, **kwargs)
