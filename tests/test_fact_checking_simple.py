"""Simplified test suite for fact-checking system."""

import pytest
import asyncio
import json
import tempfile
import os
from datetime import datetime, timezone

from debate_claim_extractor.fact_checking.fact_models import (
    FactCheckResult, VerificationSource, VerificationStatus, 
    AggregatedVerification, FactCheckConfig, SourceType
)
from debate_claim_extractor.fact_checking.services.local_service import LocalFactCheckService
from debate_claim_extractor.fact_checking.fact_pipeline import FactVerificationPipeline


class TestFactCheckModels:
    """Test fact-checking data models."""
    
    def test_fact_check_result_creation(self):
        """Test FactCheckResult model creation."""
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
        assert result.status == VerificationStatus.VERIFIED_TRUE
        assert result.confidence == 0.95
        assert len(result.sources) == 1
    
    def test_verification_source_serialization(self):
        """Test VerificationSource datetime serialization."""
        now = datetime.now(timezone.utc)
        source = VerificationSource(
            name="Test Source",
            url="https://test.com",
            source_type=SourceType.ACADEMIC,
            credibility_score=0.9,
            date_published=now
        )
        
        data = source.model_dump()
        assert isinstance(data["date_published"], str)
        assert data["date_published"] == now.isoformat()
    
    def test_aggregated_verification_creation(self):
        """Test AggregatedVerification model."""
        aggregated = AggregatedVerification(
            claim_id="test_claim_123",
            claim_text="Test claim",
            overall_status=VerificationStatus.LIKELY_TRUE,
            overall_score=0.8,
            confidence=0.8,
            sources_count=2,
            services_used=["local", "google"]
        )
        
        assert aggregated.overall_status == VerificationStatus.LIKELY_TRUE
        assert aggregated.confidence == 0.8
        assert aggregated.sources_count == 2


class TestLocalFactCheckService:
    """Test local fact-checking service."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_local_service_creation(self, temp_db_path):
        """Test local service can be created and is available."""
        service = LocalFactCheckService(database_path=temp_db_path)
        assert service.name == "local_database"
        assert service.is_available()
    
    @pytest.mark.asyncio
    async def test_verify_claim_no_match(self, temp_db_path):
        """Test claim verification when no matches found."""
        service = LocalFactCheckService(database_path=temp_db_path)
        
        result = await service.verify_claim("The moon is made of cheese")
        
        assert result.status == VerificationStatus.UNVERIFIED
        assert result.claim_text == "The moon is made of cheese"
        assert len(result.sources) == 0


class TestFactVerificationPipeline:
    """Test the fact verification pipeline."""
    
    @pytest.mark.asyncio
    async def test_pipeline_creation(self, tmp_path):
        """Test pipeline creation and basic functionality."""
        config = FactCheckConfig(timeout_seconds=30)
        pipeline = FactVerificationPipeline(config=config)
        
        # Should initialize without errors
        assert pipeline.config.timeout_seconds == 30
        assert isinstance(pipeline.services, list)
    
    @pytest.mark.asyncio
    async def test_empty_verification(self, tmp_path):
        """Test pipeline handles no available services gracefully."""
        config = FactCheckConfig(timeout_seconds=10)
        pipeline = FactVerificationPipeline(config=config)
        
        # Clear all services to test empty case
        pipeline.services = []
        
        from debate_claim_extractor.models import Claim, ClaimType
        claim = Claim(
            text="Test claim",
            claim_type=ClaimType.FACTUAL,
            confidence=0.9
        )
        
        result = await pipeline.verify_claim(claim)
        
        # Should return a result indicating no verification possible
        assert result.claim_text == "Test claim"
        assert result.overall_status == VerificationStatus.UNVERIFIED


class TestIntegration:
    """Simple integration tests."""
    
    @pytest.mark.asyncio
    async def test_basic_pipeline_flow(self, tmp_path):
        """Test basic pipeline flow with local service."""
        # Create pipeline with local service
        config = FactCheckConfig(timeout_seconds=30)
        pipeline = FactVerificationPipeline(config=config)
        
        # Add local service
        db_path = tmp_path / "test.db"
        local_service = LocalFactCheckService(database_path=str(db_path))
        pipeline.services = [local_service]  # Add service directly
        
        from debate_claim_extractor.models import Claim, ClaimType
        claim = Claim(
            text="Climate change is not real",
            claim_type=ClaimType.FACTUAL,
            confidence=0.9
        )
        
        result = await pipeline.verify_claim(claim)
        
        # Should get a result (even if unverified due to no matches)
        assert result.claim_text == "Climate change is not real"
        assert isinstance(result.overall_status, VerificationStatus)
    
    def test_json_serialization(self):
        """Test basic JSON serialization works."""
        result = FactCheckResult(
            service_name="test_service",
            query="Test claim",
            claim_text="Test claim",
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
        
        # Should serialize without errors
        json_str = json.dumps(result.model_dump())
        assert "verified_true" in json_str
        assert "Test Source" in json_str
        
        # Should be deserializable
        data = json.loads(json_str)
        assert data["status"] == "verified_true"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
