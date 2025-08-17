"""
Unit tests for the debate claim extraction pipeline
"""

import pytest
from pathlib import Path

from debate_claim_extractor.pipeline import ClaimExtractionPipeline
from debate_claim_extractor.pipeline.preprocessor import DebatePreprocessor
from debate_claim_extractor.pipeline.segmenter import DebateSegmenter
from debate_claim_extractor.pipeline.models import ClaimType


# Sample test data
SAMPLE_DEBATE_TEXT = """
MODERATOR: Welcome to tonight's debate on economic policy.

CANDIDATE A: Unemployment has decreased by 15% over the last year due to our economic policies.

CANDIDATE B: That statistic is misleading because it doesn't account for underemployment. In 2008, we saw similar patterns during the financial crisis.

MODERATOR: Can you elaborate on your policy proposals?

CANDIDATE A: My plan is better than my opponent's plan because it creates more jobs and reduces the deficit.
"""


class TestDebatePreprocessor:
    """Test the debate text preprocessor"""
    
    def test_speaker_identification(self):
        processor = DebatePreprocessor()
        utterances = processor.process(SAMPLE_DEBATE_TEXT)
        
        assert len(utterances) > 0
        
        # Check that speakers were identified correctly
        speakers = {speaker for speaker, _, _ in utterances}
        expected_speakers = {'MODERATOR', 'A', 'B'}  # Normalized names
        assert expected_speakers.issubset(speakers)
    
    def test_stage_direction_removal(self):
        text_with_directions = "SPEAKER: This is a statement (applause) with stage directions."
        processor = DebatePreprocessor()
        utterances = processor.process(text_with_directions)
        
        # Should have removed the (applause) part
        assert len(utterances) == 1
        speaker, utterance, _ = utterances[0]
        assert "(applause)" not in utterance


class TestDebateSegmenter:
    """Test the sentence segmentation"""
    
    def test_sentence_segmentation(self):
        processor = DebatePreprocessor()
        segmenter = DebateSegmenter()
        
        utterances = processor.process(SAMPLE_DEBATE_TEXT)
        sentences = segmenter.segment(utterances)
        
        assert len(sentences) > 0
        
        # Check that sentences have proper metadata
        for sentence in sentences:
            assert sentence.text.strip()  # Not empty
            assert sentence.speaker in {'MODERATOR', 'A', 'B'}
            assert sentence.char_start >= 0
            assert sentence.char_end > sentence.char_start


class TestClaimDetection:
    """Test claim detection functionality"""
    
    def test_statistical_claims(self):
        pipeline = ClaimExtractionPipeline()
        result = pipeline.extract(SAMPLE_DEBATE_TEXT)
        
        # Should find statistical claims like "15%", "2008"
        statistical_claims = [c for c in result.claims if c.type == ClaimType.STATISTICAL]
        assert len(statistical_claims) > 0
        
        # Verify one of the statistical claims
        percentage_claim = next((c for c in statistical_claims if "15%" in c.text), None)
        assert percentage_claim is not None
        assert percentage_claim.speaker == "A"
    
    def test_causal_claims(self):
        pipeline = ClaimExtractionPipeline()
        result = pipeline.extract(SAMPLE_DEBATE_TEXT)
        
        # Should find causal claims with "due to", "because"
        causal_claims = [c for c in result.claims if c.type == ClaimType.CAUSAL]
        assert len(causal_claims) > 0
        
        # Check that causal keywords are detected
        found_causal_text = any("due to" in c.text for c in causal_claims)
        assert found_causal_text
    
    def test_historical_claims(self):
        pipeline = ClaimExtractionPipeline()
        result = pipeline.extract(SAMPLE_DEBATE_TEXT)
        
        # Should find historical reference to "2008"
        historical_claims = [c for c in result.claims if c.type == ClaimType.HISTORICAL]
        assert len(historical_claims) > 0
        
        # Check for the 2008 reference
        year_claim = next((c for c in historical_claims if "2008" in c.text), None)
        assert year_claim is not None
    
    def test_comparative_claims(self):
        pipeline = ClaimExtractionPipeline()
        result = pipeline.extract(SAMPLE_DEBATE_TEXT)
        
        # Should find comparative claims like "better than"
        comparative_claims = [c for c in result.claims if c.type == ClaimType.COMPARATIVE]
        assert len(comparative_claims) > 0
        
        better_claim = next((c for c in comparative_claims if "better than" in c.text), None)
        assert better_claim is not None


class TestPipelineIntegration:
    """Test the complete pipeline integration"""
    
    def test_full_pipeline(self):
        pipeline = ClaimExtractionPipeline()
        result = pipeline.extract(SAMPLE_DEBATE_TEXT, source="test_debate")
        
        # Basic result structure checks
        assert result.claims is not None
        assert result.meta is not None
        assert result.meta.get("source") == "test_debate"
        assert result.meta.get("claims_count") == len(result.claims)
        
        # Should find multiple types of claims
        claim_types = {claim.type for claim in result.claims}
        assert len(claim_types) >= 2  # Should find at least 2 different types
        
        # All claims should have required fields
        for claim in result.claims:
            assert claim.id
            assert claim.text.strip()
            assert claim.speaker
            assert claim.confidence > 0
            assert claim.type in ClaimType
    
    def test_empty_input(self):
        pipeline = ClaimExtractionPipeline()
        result = pipeline.extract("", source="empty_test")
        
        assert len(result.claims) == 0
        assert "error" in result.meta or result.meta.get("claims_count") == 0
    
    def test_metadata_completeness(self):
        pipeline = ClaimExtractionPipeline()
        result = pipeline.extract(SAMPLE_DEBATE_TEXT)
        
        # Check required metadata fields
        required_fields = ["generated_at", "claims_count", "speakers"]
        for field in required_fields:
            assert field in result.meta
        
        # Check claim type breakdown
        assert "claim_types" in result.meta
        claim_type_counts = result.meta["claim_types"]
        
        # Should sum to total claims
        total_from_breakdown = sum(claim_type_counts.values())
        assert total_from_breakdown == len(result.claims)


# Sample tests for real file processing
class TestFileProcessing:
    """Test processing of actual files"""
    
    def test_sample_transcript_processing(self):
        sample_file = Path(__file__).parent.parent / "sample_transcript.txt"
        
        if sample_file.exists():
            pipeline = ClaimExtractionPipeline()
            
            with open(sample_file, 'r') as f:
                text = f.read()
            
            result = pipeline.extract(text, source=str(sample_file))
            
            # Should find multiple claims in the sample transcript
            assert len(result.claims) >= 5
            
            # Should identify all the speakers
            speakers = result.meta.get("speakers", [])
            expected_speakers = {"MODERATOR", "A", "B"}  # Normalized
            assert expected_speakers.issubset(set(speakers))
            
            # Should find various claim types
            claim_types = {claim.type for claim in result.claims}
            assert ClaimType.STATISTICAL in claim_types
            assert ClaimType.HISTORICAL in claim_types
