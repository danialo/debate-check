"""
Google Fact Check Tools API integration
"""

import os
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

from .base_service import RateLimitedService
from ..fact_models import (
    FactCheckResult, 
    VerificationSource,
    VerificationStatus,
    SourceType,
    get_source_credibility
)


class GoogleFactCheckService(RateLimitedService):
    """Google Fact Check Tools API integration"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(
            name="google_fact_check",
            base_url="https://factchecktools.googleapis.com/v1alpha1",
            requests_per_minute=16,  # Conservative rate for free tier (1000/day)
            **kwargs
        )
        
        self.api_key = api_key or os.getenv("GOOGLE_FACT_CHECK_API_KEY")
        
    def is_available(self) -> bool:
        """Check if Google Fact Check API is available"""
        return bool(self.api_key)
    
    async def verify_claim(self, claim_text: str, **kwargs) -> FactCheckResult:
        """
        Verify claim using Google Fact Check Tools API
        
        Args:
            claim_text: Claim text to verify
            **kwargs: Additional parameters (language_code, page_size, etc.)
            
        Returns:
            FactCheckResult with verification data
        """
        if not self.is_available():
            return self.create_error_result(
                claim_text, 
                "Google Fact Check API key not configured"
            )
        
        # Preprocess the claim for better API results
        query = self.preprocess_claim(claim_text)
        
        try:
            # Build query parameters
            params = {
                'key': self.api_key,
                'query': query,
                'pageSize': kwargs.get('page_size', 10),
                'offset': kwargs.get('offset', 0)
            }
            
            if 'language_code' in kwargs:
                params['languageCode'] = kwargs['language_code']
            
            # Make API request
            endpoint = f"claims:search?{urlencode(params)}"
            data = await self._make_request('GET', endpoint)
            
            if not data:
                return self.create_error_result(claim_text, "API request failed", query)
            
            # Parse response and create result
            return self._parse_google_response(claim_text, query, data)
            
        except Exception as e:
            self.logger.error(f"Google Fact Check API error: {e}")
            return self.create_error_result(claim_text, str(e), query)
    
    def _parse_google_response(self, 
                              claim_text: str, 
                              query: str, 
                              data: Dict[str, Any]) -> FactCheckResult:
        """
        Parse Google Fact Check API response
        
        Args:
            claim_text: Original claim text
            query: Query sent to API
            data: API response data
            
        Returns:
            FactCheckResult with parsed data
        """
        claims = data.get('claims', [])
        
        if not claims:
            return FactCheckResult(
                service_name=self.name,
                query=query,
                claim_text=claim_text,
                status=VerificationStatus.UNVERIFIED,
                confidence=0.0,
                verification_score=0.5,
                explanation="No fact-checks found for this claim",
                sources=[]
            )
        
        # Parse all fact-check sources
        sources = []
        all_ratings = []
        explanations = []
        
        for claim in claims[:5]:  # Limit to top 5 results
            claim_reviews = claim.get('claimReview', [])
            
            for review in claim_reviews:
                # Extract source information
                publisher = review.get('publisher', {})
                source = self._create_verification_source(publisher, review)
                sources.append(source)
                
                # Extract rating information
                rating = self._parse_rating(review.get('textualRating', ''))
                if rating is not None:
                    all_ratings.append(rating)
                
                # Collect explanations
                if review.get('reviewBody'):
                    explanations.append(review['reviewBody'][:200])
        
        # Calculate aggregated verification score
        if all_ratings:
            avg_rating = sum(all_ratings) / len(all_ratings)
            confidence = min(0.9, len(all_ratings) * 0.2)  # More sources = higher confidence
        else:
            avg_rating = 0.5  # Neutral if no ratings
            confidence = 0.1
        
        # Determine status from score
        status = self._score_to_status(avg_rating)
        
        # Create summary explanation
        explanation = self._create_explanation(sources, explanations, status)
        
        return FactCheckResult(
            service_name=self.name,
            query=query,
            claim_text=claim_text,
            status=status,
            confidence=confidence,
            verification_score=avg_rating,
            sources=sources,
            explanation=explanation,
            api_response_raw=data  # Store for debugging
        )
    
    def _create_verification_source(self, 
                                   publisher: Dict[str, Any], 
                                   review: Dict[str, Any]) -> VerificationSource:
        """Create VerificationSource from Google API data"""
        
        name = publisher.get('name', 'Unknown Publisher')
        url = review.get('url', '')
        
        # Determine source type and credibility
        source_type = SourceType.PROFESSIONAL_FACT_CHECKER
        credibility = get_source_credibility(name)
        
        # Parse date
        date_published = None
        date_str = review.get('datePublished')
        if date_str:
            try:
                date_published = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass
        
        return VerificationSource(
            name=name,
            url=url,
            source_type=source_type,
            credibility_score=credibility,
            date_published=date_published,
            author=review.get('author', {}).get('name')
        )
    
    def _parse_rating(self, textual_rating: str) -> Optional[float]:
        """
        Parse textual rating to numeric score
        
        Args:
            textual_rating: Rating text from API (e.g., "True", "False", "Mostly True")
            
        Returns:
            Numeric score 0.0-1.0 or None if unparseable
        """
        if not textual_rating:
            return None
        
        rating = textual_rating.lower().strip()
        
        # True ratings (0.7-1.0)
        if any(word in rating for word in ['true', 'correct', 'accurate', 'verified']):
            if any(qualifier in rating for qualifier in ['mostly', 'largely', 'generally']):
                return 0.8
            elif any(qualifier in rating for qualifier in ['partly', 'partially', 'somewhat']):
                return 0.6
            else:
                return 0.9  # Fully true
        
        # False ratings (0.0-0.3)
        elif any(word in rating for word in ['false', 'incorrect', 'wrong', 'debunked']):
            if any(qualifier in rating for qualifier in ['mostly', 'largely', 'generally']):
                return 0.2
            elif any(qualifier in rating for qualifier in ['partly', 'partially', 'somewhat']):
                return 0.4
            else:
                return 0.1  # Fully false
        
        # Mixed/unclear ratings (0.4-0.6)
        elif any(word in rating for word in ['mixed', 'unclear', 'unproven', 'disputed']):
            return 0.5
        
        # Half true/misleading (0.3-0.7)
        elif any(word in rating for word in ['half', 'misleading', 'lacks context']):
            return 0.4
        
        # Unable to determine
        return None
    
    def _score_to_status(self, score: float) -> VerificationStatus:
        """Convert numeric score to verification status"""
        if score >= 0.8:
            return VerificationStatus.VERIFIED_TRUE
        elif score >= 0.6:
            return VerificationStatus.LIKELY_TRUE
        elif score >= 0.4:
            return VerificationStatus.MIXED
        elif score >= 0.2:
            return VerificationStatus.LIKELY_FALSE
        else:
            return VerificationStatus.VERIFIED_FALSE
    
    def _create_explanation(self, 
                           sources: List[VerificationSource], 
                           explanations: List[str],
                           status: VerificationStatus) -> str:
        """Create human-readable explanation of verification"""
        
        if not sources:
            return "No fact-check sources found for this claim."
        
        source_count = len(sources)
        top_sources = sorted(sources, key=lambda s: s.credibility_score, reverse=True)[:3]
        source_names = [s.name for s in top_sources]
        
        explanation_parts = [
            f"Found {source_count} fact-check(s) from sources including: {', '.join(source_names)}"
        ]
        
        # Add status explanation
        status_explanations = {
            VerificationStatus.VERIFIED_TRUE: "Multiple sources confirm this claim as true.",
            VerificationStatus.LIKELY_TRUE: "Most sources indicate this claim is likely true.",
            VerificationStatus.MIXED: "Sources show mixed evidence for this claim.",
            VerificationStatus.LIKELY_FALSE: "Most sources indicate this claim is likely false.",
            VerificationStatus.VERIFIED_FALSE: "Multiple sources confirm this claim as false."
        }
        
        if status in status_explanations:
            explanation_parts.append(status_explanations[status])
        
        # Add sample explanation if available
        if explanations:
            explanation_parts.append(f"Example: {explanations[0]}")
        
        return " ".join(explanation_parts)
