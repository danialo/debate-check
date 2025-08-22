"""Mock services and test data for fact-checking system testing."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from debate_claim_extractor.fact_checking.fact_models import (
    FactCheckResult, VerificationSource, VerificationStatus
)
from debate_claim_extractor.fact_checking.services.base_service import FactCheckService


class MockGoogleFactCheckService(BaseFactCheckService):
    """Mock implementation of Google Fact Check Service for testing."""
    
    def __init__(self, mock_responses: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        """Initialize with optional mock responses."""
        super().__init__(name="MockGoogle")
        self.mock_responses = mock_responses or self._get_default_responses()
        self.call_count = 0
        self.last_query = None
    
    def _get_default_responses(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get default mock responses for common claims."""
        return {
            "vaccines are safe": [
                {
                    "status": VerificationStatus.VERIFIED_TRUE,
                    "confidence": 0.95,
                    "source": "CDC Official",
                    "url": "https://cdc.gov/vaccines-safety",
                    "credibility": 0.95
                }
            ],
            "climate change is a hoax": [
                {
                    "status": VerificationStatus.VERIFIED_FALSE,
                    "confidence": 0.98,
                    "source": "NASA Climate",
                    "url": "https://nasa.gov/climate-reality",
                    "credibility": 0.9
                }
            ],
            "earth is flat": [
                {
                    "status": VerificationStatus.VERIFIED_FALSE,
                    "confidence": 0.99,
                    "source": "Scientific Consensus",
                    "url": "https://science.org/earth-spherical",
                    "credibility": 0.95
                }
            ],
            "unemployment rate decreased": [
                {
                    "status": VerificationStatus.LIKELY_TRUE,
                    "confidence": 0.75,
                    "source": "Bureau of Labor Statistics",
                    "url": "https://bls.gov/unemployment",
                    "credibility": 0.85
                }
            ]
        }
    
    async def verify_claim(self, claim_text: str) -> List[FactCheckResult]:
        """Mock claim verification with simulated API delay."""
        self.call_count += 1
        self.last_query = claim_text
        
        # Simulate API delay
        await asyncio.sleep(0.1)
        
        # Find matching mock response
        claim_lower = claim_text.lower()
        for key, responses in self.mock_responses.items():
            if key.lower() in claim_lower or any(word in claim_lower for word in key.split()):
                results = []
                for resp in responses:
                    source = VerificationSource(
                        name=resp["source"],
                        url=resp["url"],
                        credibility_score=resp["credibility"],
                        last_updated=datetime.now(timezone.utc)
                    )
                    
                    result = FactCheckResult(
                        claim_text=claim_text,
                        verification_status=resp["status"],
                        confidence_score=resp["confidence"],
                        sources=[source]
                    )
                    results.append(result)
                
                return results
        
        # No match found
        return []


class MockLocalFactCheckService(BaseFactCheckService):
    """Mock implementation of Local Fact Check Service for testing."""
    
    def __init__(self, test_database: Optional[List[Dict[str, Any]]] = None):
        """Initialize with optional test database."""
        super().__init__(name="MockLocal")
        self.database = test_database or self._get_default_database()
        self.call_count = 0
    
    def _get_default_database(self) -> List[Dict[str, Any]]:
        """Get default test database entries."""
        return [
            {
                "claim": "The sky is blue",
                "status": VerificationStatus.VERIFIED_TRUE,
                "confidence": 0.99,
                "source": "Physics Textbook",
                "url": "https://physics.org/sky-color",
                "credibility": 0.9
            },
            {
                "claim": "Water boils at 100°C at sea level",
                "status": VerificationStatus.VERIFIED_TRUE,
                "confidence": 0.99,
                "source": "Chemistry Reference",
                "url": "https://chemistry.org/boiling-point",
                "credibility": 0.95
            },
            {
                "claim": "Smoking is healthy",
                "status": VerificationStatus.VERIFIED_FALSE,
                "confidence": 0.99,
                "source": "WHO Health Report",
                "url": "https://who.int/smoking-health",
                "credibility": 0.95
            }
        ]
    
    async def verify_claim(self, claim_text: str) -> List[FactCheckResult]:
        """Mock local database lookup with text similarity."""
        self.call_count += 1
        
        # Simulate database lookup delay
        await asyncio.sleep(0.05)
        
        results = []
        claim_lower = claim_text.lower()
        
        for entry in self.database:
            entry_claim_lower = entry["claim"].lower()
            
            # Simple similarity check
            if (claim_lower in entry_claim_lower or 
                entry_claim_lower in claim_lower or
                self._calculate_word_overlap(claim_lower, entry_claim_lower) > 0.3):
                
                source = VerificationSource(
                    name=entry["source"],
                    url=entry["url"],
                    credibility_score=entry["credibility"],
                    last_updated=datetime.now(timezone.utc)
                )
                
                result = FactCheckResult(
                    claim_text=claim_text,
                    verification_status=entry["status"],
                    confidence_score=entry["confidence"],
                    sources=[source]
                )
                results.append(result)
        
        return results
    
    def _calculate_word_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap between two texts."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)


class MockFailingService(BaseFactCheckService):
    """Mock service that always fails for testing error handling."""
    
    def __init__(self, error_type: type = Exception, error_message: str = "Mock service error"):
        """Initialize with configurable error."""
        super().__init__(name="MockFailing")
        self.error_type = error_type
        self.error_message = error_message
        self.call_count = 0
    
    async def verify_claim(self, claim_text: str) -> List[FactCheckResult]:
        """Always raise an error."""
        self.call_count += 1
        await asyncio.sleep(0.05)  # Brief delay before failing
        raise self.error_type(self.error_message)


class MockSlowService(BaseFactCheckService):
    """Mock service that times out for testing timeout handling."""
    
    def __init__(self, delay_seconds: float = 5.0):
        """Initialize with configurable delay."""
        super().__init__(name="MockSlow")
        self.delay_seconds = delay_seconds
        self.call_count = 0
    
    async def verify_claim(self, claim_text: str) -> List[FactCheckResult]:
        """Always timeout."""
        self.call_count += 1
        await asyncio.sleep(self.delay_seconds)
        
        # This should never be reached in timeout tests
        return [
            FactCheckResult(
                claim_text=claim_text,
                verification_status=VerificationStatus.UNVERIFIED,
                confidence_score=0.5,
                sources=[]
            )
        ]


class TestDataGenerator:
    """Generate test data for fact-checking system testing."""
    
    @staticmethod
    def generate_test_claims() -> List[str]:
        """Generate a set of test claims covering various topics."""
        return [
            "Vaccines prevent diseases and are generally safe",
            "Climate change is caused by human activities",
            "The Earth is approximately 4.5 billion years old",
            "Smoking cigarettes increases the risk of lung cancer",
            "The COVID-19 pandemic started in 2019",
            "Water freezes at 0 degrees Celsius",
            "The Great Wall of China is visible from space",
            "Lightning never strikes the same place twice",
            "We only use 10% of our brains",
            "Goldfish have a three-second memory",
            "Antibiotics are effective against viral infections",
            "The moon landing was staged by NASA"
        ]
    
    @staticmethod
    def generate_factual_claims() -> List[str]:
        """Generate claims that should be verifiable as true."""
        return [
            "The sun is a star",
            "Water is composed of hydrogen and oxygen",
            "The human body has 206 bones",
            "DNA stands for deoxyribonucleic acid",
            "The speed of light is approximately 300,000 km/s"
        ]
    
    @staticmethod
    def generate_false_claims() -> List[str]:
        """Generate claims that should be verifiable as false."""
        return [
            "The Earth is flat",
            "Vaccines cause autism",
            "Climate change is not real",
            "The moon is made of cheese",
            "Humans only use 10% of their brain"
        ]
    
    @staticmethod
    def generate_ambiguous_claims() -> List[str]:
        """Generate claims that are hard to verify definitively."""
        return [
            "The economy will improve next year",
            "Artificial intelligence will replace most jobs",
            "Space travel will become common in our lifetime",
            "Social media makes people happier",
            "Remote work is more productive than office work"
        ]
    
    @staticmethod
    def generate_mixed_verification_dataset() -> Dict[str, List[str]]:
        """Generate a comprehensive dataset with various verification outcomes."""
        return {
            "verifiable_true": TestDataGenerator.generate_factual_claims(),
            "verifiable_false": TestDataGenerator.generate_false_claims(),
            "ambiguous": TestDataGenerator.generate_ambiguous_claims(),
            "general": TestDataGenerator.generate_test_claims()
        }


class MockResponseBuilder:
    """Builder for creating mock API responses."""
    
    @staticmethod
    def build_google_api_response(claim_text: str, rating: str = "True", 
                                publisher_name: str = "Test Publisher") -> Dict[str, Any]:
        """Build a mock Google Fact Check API response."""
        return {
            "claims": [
                {
                    "text": claim_text,
                    "claimReview": [
                        {
                            "publisher": {
                                "name": publisher_name,
                                "site": "testpublisher.com"
                            },
                            "url": f"https://testpublisher.com/fact-check/{claim_text.replace(' ', '-').lower()}",
                            "title": f"Fact Check: {claim_text}",
                            "reviewRating": {
                                "ratingValue": 5 if rating == "True" else 1,
                                "bestRating": 5,
                                "alternateName": rating
                            },
                            "datePublished": "2024-01-01T00:00:00Z"
                        }
                    ]
                }
            ]
        }
    
    @staticmethod
    def build_multiple_reviews_response(claim_text: str) -> Dict[str, Any]:
        """Build a response with multiple fact-check reviews."""
        return {
            "claims": [
                {
                    "text": claim_text,
                    "claimReview": [
                        {
                            "publisher": {"name": "Fact Checker 1", "site": "checker1.com"},
                            "url": "https://checker1.com/fact-check",
                            "title": f"Review: {claim_text}",
                            "reviewRating": {
                                "ratingValue": 4,
                                "bestRating": 5,
                                "alternateName": "Mostly True"
                            },
                            "datePublished": "2024-01-01T00:00:00Z"
                        },
                        {
                            "publisher": {"name": "Fact Checker 2", "site": "checker2.com"},
                            "url": "https://checker2.com/fact-check",
                            "title": f"Analysis: {claim_text}",
                            "reviewRating": {
                                "ratingValue": 3,
                                "bestRating": 5,
                                "alternateName": "Half True"
                            },
                            "datePublished": "2024-01-02T00:00:00Z"
                        }
                    ]
                }
            ]
        }


class TestEnvironmentManager:
    """Manage test environments for fact-checking system."""
    
    def __init__(self):
        """Initialize test environment manager."""
        self.services = {}
        self.test_data = TestDataGenerator()
    
    def create_mock_environment(self, include_failing: bool = False, 
                               include_slow: bool = False) -> Dict[str, BaseFactCheckService]:
        """Create a complete mock testing environment."""
        services = {
            "google": MockGoogleFactCheckService(),
            "local": MockLocalFactCheckService()
        }
        
        if include_failing:
            services["failing"] = MockFailingService()
        
        if include_slow:
            services["slow"] = MockSlowService()
        
        return services
    
    def get_test_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Get various test scenarios."""
        return {
            "normal_operation": {
                "services": ["google", "local"],
                "expected_results": "both_services_respond"
            },
            "google_only": {
                "services": ["google"],
                "expected_results": "single_service_response"
            },
            "local_only": {
                "services": ["local"],
                "expected_results": "single_service_response"
            },
            "with_failures": {
                "services": ["google", "local", "failing"],
                "expected_results": "partial_failure_handling"
            },
            "with_timeouts": {
                "services": ["google", "slow"],
                "expected_results": "timeout_handling"
            }
        }


# Example usage and test helper functions
async def run_mock_test_scenario():
    """Example function showing how to use mock services for testing."""
    # Create mock services
    google_mock = MockGoogleFactCheckService()
    local_mock = MockLocalFactCheckService()
    
    # Test a claim
    test_claim = "vaccines are safe"
    
    print(f"Testing claim: {test_claim}")
    
    # Test Google mock
    google_results = await google_mock.verify_claim(test_claim)
    print(f"Google mock returned {len(google_results)} results")
    for result in google_results:
        print(f"  - {result.verification_status.value} (confidence: {result.confidence_score})")
    
    # Test Local mock
    local_results = await local_mock.verify_claim(test_claim)
    print(f"Local mock returned {len(local_results)} results")
    for result in local_results:
        print(f"  - {result.verification_status.value} (confidence: {result.confidence_score})")


if __name__ == "__main__":
    # Run example test
    asyncio.run(run_mock_test_scenario())
