"""Comprehensive test suite for fact-checking system."""

import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from datetime import datetime, timezone

from debate_claim_extractor.fact_checking.fact_models import (
    FactCheckResult, VerificationSource, VerificationStatus, 
    AggregatedVerification, FactCheckConfig, SourceType
)
from debate_claim_extractor.fact_checking.services.base_service import FactCheckService
from debate_claim_extractor.fact_checking.services.google_service import GoogleFactCheckService
from debate_claim_extractor.fact_checking.services.local_service import LocalFactCheckService
from debate_claim_extractor.fact_checking.fact_pipeline import FactVerificationPipeline
from debate_claim_extractor.models import Claim, ClaimType


class TestFactCheckModels:
    """Test fact-checking data models."""
    
    def test_fact_check_result_creation(self):
        """Test FactCheckResult model creation and serialization."""
        result = FactCheckResult(
            service_name="test_service",
            query="The sky is blue",
            claim_text="The sky is blue",
            status=VerificationStatus.VERIFIED_TRUE,
            confidence=0.95,
            verification_score=0.95,
            sources=[
                VerificationSource(
                    name="Test Source",
                    url="https://test.com",
                    source_type=SourceType.ACADEMIC,
                    credibility_score=0.9,
                    date_published=datetime.now(timezone.utc)
                )
            ]
        )
        
        assert result.claim_text == "The sky is blue"
        assert result.verification_status == VerificationStatus.VERIFIED_TRUE
        assert result.confidence_score == 0.95
        assert len(result.sources) == 1
        
        # Test serialization
        data = result.model_dump()
        assert data["claim_text"] == "The sky is blue"
        assert data["verification_status"] == "VERIFIED_TRUE"
    
    def test_verification_source_datetime_handling(self):
        """Test datetime serialization in VerificationSource."""
        now = datetime.now(timezone.utc)
        source = VerificationSource(
            name="Test Source",
            url="https://test.com",
            credibility_score=0.9,
            last_updated=now
        )
        
        data = source.model_dump()
        assert isinstance(data["last_updated"], str)
        assert data["last_updated"] == now.isoformat()
    
    def test_verification_summary_creation(self):
        """Test VerificationSummary model."""
        summary = VerificationSummary(
            overall_status=VerificationStatus.LIKELY_TRUE,
            overall_confidence=0.8,
            services_used=2,
            sources_found=5,
            summary_text="Likely true based on multiple sources"
        )
        
        assert summary.overall_status == VerificationStatus.LIKELY_TRUE
        assert summary.overall_confidence == 0.8
        assert summary.services_used == 2


class TestLocalFactCheckService:
    """Test local fact-checking service."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)
    
    @pytest.fixture
    def local_service(self, temp_db_path):
        """Create LocalFactCheckService with test data."""
        service = LocalFactCheckService(db_path=temp_db_path)
        
        # Add test data
        test_data = [
            {
                "claim": "Vaccines are safe and effective",
                "status": "VERIFIED_TRUE",
                "confidence": 0.95,
                "source": "CDC",
                "url": "https://cdc.gov/vaccines"
            },
            {
                "claim": "Climate change is a hoax",
                "status": "VERIFIED_FALSE", 
                "confidence": 0.98,
                "source": "NASA",
                "url": "https://nasa.gov/climate"
            }
        ]
        
        asyncio.run(service._populate_test_data(test_data))
        return service
    
    @pytest.mark.asyncio
    async def test_exact_match(self, local_service):
        """Test exact claim matching."""
        results = await local_service.verify_claim("Vaccines are safe and effective")
        
        assert len(results) == 1
        result = results[0]
        assert result.verification_status == VerificationStatus.VERIFIED_TRUE
        assert result.confidence_score == 0.95
        assert len(result.sources) == 1
        assert result.sources[0].name == "CDC"
    
    @pytest.mark.asyncio
    async def test_similarity_matching(self, local_service):
        """Test similar claim matching."""
        results = await local_service.verify_claim("Are vaccines safe?")
        
        assert len(results) >= 1
        # Should find the vaccine claim with good similarity
        vaccine_result = next(
            r for r in results 
            if "vaccine" in r.claim_text.lower()
        )
        assert vaccine_result.verification_status == VerificationStatus.VERIFIED_TRUE
    
    @pytest.mark.asyncio
    async def test_no_match(self, local_service):
        """Test when no matching claims are found."""
        results = await local_service.verify_claim("The moon is made of cheese")
        
        assert len(results) == 0


class TestGoogleFactCheckService:
    """Test Google Fact Check Tools API service."""
    
    @pytest.fixture
    def google_service(self):
        """Create GoogleFactCheckService for testing."""
        return GoogleFactCheckService(api_key="test_api_key")
    
    @pytest.mark.asyncio
    async def test_api_call_structure(self, google_service):
        """Test API call structure without making real requests."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = Mock()
            mock_response.json = AsyncMock(return_value={"claims": []})
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response
            
            results = await google_service.verify_claim("Test claim")
            
            # Verify API was called with correct parameters
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "query" in call_args[1]["params"]
            assert call_args[1]["params"]["query"] == "Test claim"
    
    @pytest.mark.asyncio
    async def test_response_parsing(self, google_service):
        """Test parsing of Google API responses."""
        mock_response_data = {
            "claims": [
                {
                    "text": "Test claim",
                    "claimReview": [
                        {
                            "publisher": {"name": "Test Publisher", "site": "test.com"},
                            "url": "https://test.com/fact-check",
                            "title": "Fact Check: Test claim",
                            "reviewRating": {
                                "ratingValue": 5,
                                "bestRating": 5,
                                "alternateName": "True"
                            },
                            "datePublished": "2024-01-01"
                        }
                    ]
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = Mock()
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response
            
            results = await google_service.verify_claim("Test claim")
            
            assert len(results) == 1
            result = results[0]
            assert result.claim_text == "Test claim"
            assert result.verification_status == VerificationStatus.VERIFIED_TRUE
            assert len(result.sources) == 1
            assert result.sources[0].name == "Test Publisher"


class TestFactVerificationPipeline:
    """Test the fact verification pipeline."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock fact-checking services."""
        local_service = Mock(spec=LocalFactCheckService)
        google_service = Mock(spec=GoogleFactCheckService)
        
        # Mock local service results
        local_result = FactCheckResult(
            claim_text="Test claim",
            verification_status=VerificationStatus.VERIFIED_TRUE,
            confidence_score=0.9,
            sources=[
                VerificationSource(
                    name="Local DB",
                    url="local://test",
                    credibility_score=0.8
                )
            ]
        )
        local_service.verify_claim = AsyncMock(return_value=[local_result])
        
        # Mock Google service results
        google_result = FactCheckResult(
            claim_text="Test claim",
            verification_status=VerificationStatus.LIKELY_TRUE,
            confidence_score=0.85,
            sources=[
                VerificationSource(
                    name="Google Fact Check",
                    url="https://google.com/factcheck",
                    credibility_score=0.9
                )
            ]
        )
        google_service.verify_claim = AsyncMock(return_value=[google_result])
        
        return {"local": local_service, "google": google_service}
    
    @pytest.fixture
    def pipeline(self, mock_services):
        """Create FactVerificationPipeline with mock services."""
        config = FactCheckConfig(timeout_seconds=30)
        pipeline = FactVerificationPipeline(config=config)
        pipeline.services = list(mock_services.values())
        return pipeline
    
    @pytest.mark.asyncio
    async def test_single_claim_verification(self, pipeline, mock_services):
        """Test verification of a single claim."""
        claim = Claim(
            text="Test claim",
            claim_type=ClaimType.FACTUAL,
            confidence=0.9
        )
        
        result = await pipeline.verify_claim(claim)
        
        assert result.claim_text == "Test claim"
        assert result.verification_summary is not None
        assert result.verification_summary.services_used == 2
        assert len(result.sources) >= 2  # Should aggregate sources
    
    @pytest.mark.asyncio
    async def test_batch_verification(self, pipeline, mock_services):
        """Test batch verification of multiple claims."""
        claims = [
            Claim(text="Claim 1", claim_type=ClaimType.FACTUAL, confidence=0.9),
            Claim(text="Claim 2", claim_type=ClaimType.FACTUAL, confidence=0.8),
        ]
        
        results = await pipeline.verify_claims(claims)
        
        assert len(results) == 2
        for result in results:
            assert result.verification_summary is not None
            assert result.verification_summary.services_used == 2
    
    @pytest.mark.asyncio
    async def test_confidence_aggregation(self, pipeline, mock_services):
        """Test confidence score aggregation logic."""
        claim = Claim(
            text="Test claim",
            claim_type=ClaimType.FACTUAL,
            confidence=0.9
        )
        
        result = await pipeline.verify_claim(claim)
        
        # Should be weighted average considering credibility
        # Local: 0.9 * 0.8 = 0.72, Google: 0.85 * 0.9 = 0.765
        # Weighted average should be around 0.74-0.75
        assert 0.7 <= result.confidence_score <= 0.8
    
    @pytest.mark.asyncio
    async def test_service_timeout_handling(self, pipeline):
        """Test handling of service timeouts."""
        slow_service = Mock(spec=LocalFactCheckService)
        slow_service.verify_claim = AsyncMock(
            side_effect=asyncio.TimeoutError("Service timeout")
        )
        pipeline.services = [slow_service]
        
        claim = Claim(text="Test claim", claim_type=ClaimType.FACTUAL, confidence=0.9)
        result = await pipeline.verify_claim(claim)
        
        # Should handle timeout gracefully
        assert result.verification_status == VerificationStatus.UNVERIFIED
        assert result.verification_summary.services_used == 0


class TestIntegration:
    """Integration tests for the complete fact-checking system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(self, tmp_path):
        """Test complete end-to-end fact-checking pipeline."""
        # Create temporary database
        db_path = tmp_path / "test.db"
        
        # Initialize services
        local_service = LocalFactCheckService(db_path=str(db_path))
        
        # Create pipeline
        config = FactCheckConfig(timeout_seconds=30)
        pipeline = FactVerificationPipeline(config=config)
        pipeline.add_service(local_service)
        
        # Add test data to local database
        test_data = [
            {
                "claim": "The Earth is round",
                "status": "VERIFIED_TRUE",
                "confidence": 0.99,
                "source": "NASA",
                "url": "https://nasa.gov/earth"
            }
        ]
        await local_service._populate_test_data(test_data)
        
        # Test claim verification
        claim = Claim(
            text="The Earth is round",
            claim_type=ClaimType.FACTUAL,
            confidence=0.9
        )
        
        result = await pipeline.verify_claim(claim)
        
        assert result.verification_status == VerificationStatus.VERIFIED_TRUE
        assert result.confidence_score >= 0.9
        assert len(result.sources) >= 1
        assert result.verification_summary.services_used >= 1
    
    def test_json_serialization(self):
        """Test JSON serialization of fact-checking results."""
        result = FactCheckResult(
            claim_text="Test claim",
            verification_status=VerificationStatus.VERIFIED_TRUE,
            confidence_score=0.95,
            sources=[
                VerificationSource(
                    name="Test Source",
                    url="https://test.com",
                    credibility_score=0.9,
                    last_updated=datetime.now(timezone.utc)
                )
            ],
            verification_summary=VerificationSummary(
                overall_status=VerificationStatus.VERIFIED_TRUE,
                overall_confidence=0.95,
                services_used=1,
                sources_found=1,
                summary_text="Verified as true"
            )
        )
        
        # Should serialize without errors
        json_str = json.dumps(result.model_dump())
        assert "VERIFIED_TRUE" in json_str
        assert "Test Source" in json_str
        
        # Should be deserializable
        data = json.loads(json_str)
        assert data["verification_status"] == "VERIFIED_TRUE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
