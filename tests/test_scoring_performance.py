"""
Performance benchmarks and stress tests for the scoring system.
"""

import time
import pytest
import statistics
import random
from typing import List

from debate_claim_extractor.pipeline.models import Claim
from debate_claim_extractor.fact_checking.fact_models import FactCheckResult, VerificationStatus
from debate_claim_extractor.fallacy_detection.fallacy_models import FallacyResult, FallacyType, FallacySeverity
from debate_claim_extractor.scoring import ScoringPipeline, ScoringConfig


class TestScoringPerformance:
    """Performance and stress tests for the scoring system."""
    
    def generate_large_dataset(self, num_claims: int = 1000) -> tuple:
        """Generate a large dataset for stress testing."""
        claims = []
        fact_results = []
        fallacies = []
        
        claim_types = ["factual", "statistical", "causal", "comparative", "historical"]
        speakers = [f"SPEAKER_{i}" for i in range(10)]  # 10 different speakers
        statuses = [
            VerificationStatus.VERIFIED_TRUE,
            VerificationStatus.LIKELY_TRUE, 
            VerificationStatus.MIXED,
            VerificationStatus.LIKELY_FALSE,
            VerificationStatus.VERIFIED_FALSE
        ]
        fallacy_types = [
            FallacyType.AD_HOMINEM,
            FallacyType.STRAW_MAN,
            FallacyType.FALSE_DILEMMA,
            FallacyType.APPEAL_TO_AUTHORITY,
            FallacyType.SLIPPERY_SLOPE
        ]
        severities = [FallacySeverity.LOW, FallacySeverity.MEDIUM, FallacySeverity.HIGH]
        
        for i in range(num_claims):
            # Create claims
            claims.append(
                Claim(
                    id=f"claim_{i}",
                    type=random.choice(claim_types),
                    text=f"This is test claim number {i} with some content to make it realistic",
                    speaker=random.choice(speakers),
                    confidence=random.uniform(0.3, 1.0),
                    sentence_id=f"sent_{i}",
                    turn_id=i % 20,  # 20 turns
                    char_start=i * 50,
                    char_end=(i + 1) * 50
                )
            )
            
            # Add fact-checking results for ~30% of claims
            if random.random() < 0.3:
                fact_results.append(
                    FactCheckResult(
                        claim_id=f"claim_{i}",
                        service_name="test_service",
                        query=f"query_{i}",
                        claim_text=f"This is test claim number {i} with some content to make it realistic",
                        status=random.choice(statuses),
                        confidence=random.uniform(0.5, 1.0),
                        verification_score=random.uniform(0.0, 1.0)
                    )
                )
            
            # Add fallacies for ~10% of claims
            if random.random() < 0.1:
                fallacies.append(
                    FallacyResult(
                        id=f"fallacy_{len(fallacies)}",
                        type=random.choice(fallacy_types),
                        text=f"This is fallacy text {len(fallacies)}",
                        speaker=random.choice(speakers),
                        confidence=random.uniform(0.4, 1.0),
                        severity=random.choice(severities)
                    )
                )
        
        return claims, fact_results, fallacies
    
    def test_small_dataset_performance(self):
        """Test performance with small datasets (baseline)."""
        claims, fact_results, fallacies = self.generate_large_dataset(10)
        pipeline = ScoringPipeline()
        
        start_time = time.time()
        result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        assert result.scoring_performed is True
        assert processing_time < 0.1  # Should be very fast for 10 claims
        print(f"Small dataset (10 claims): {processing_time:.4f}s")
    
    def test_medium_dataset_performance(self):
        """Test performance with medium datasets."""
        claims, fact_results, fallacies = self.generate_large_dataset(100)
        pipeline = ScoringPipeline()
        
        start_time = time.time()
        result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        assert result.scoring_performed is True
        assert processing_time < 1.0  # Should complete within 1 second for 100 claims
        print(f"Medium dataset (100 claims): {processing_time:.4f}s")
    
    def test_large_dataset_performance(self):
        """Test performance with large datasets."""
        claims, fact_results, fallacies = self.generate_large_dataset(1000)
        pipeline = ScoringPipeline()
        
        start_time = time.time()
        result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        assert result.scoring_performed is True
        assert processing_time < 10.0  # Should complete within 10 seconds for 1000 claims
        print(f"Large dataset (1000 claims): {processing_time:.4f}s")
        
        # Verify results make sense
        assert result.debate_score.total_claims == 1000
        assert len(result.debate_score.speaker_scores) <= 10  # Max 10 speakers
    
    def test_scalability_analysis(self):
        """Test scalability across different dataset sizes."""
        sizes = [10, 50, 100, 250, 500]
        times = []
        
        for size in sizes:
            claims, fact_results, fallacies = self.generate_large_dataset(size)
            pipeline = ScoringPipeline()
            
            start_time = time.time()
            result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
            end_time = time.time()
            
            processing_time = end_time - start_time
            times.append(processing_time)
            
            assert result.scoring_performed is True
            print(f"Dataset size {size}: {processing_time:.4f}s")
        
        # Check that growth is reasonable (should be roughly linear)
        # Time per claim should not grow exponentially
        time_per_claim = [t / s for t, s in zip(times, sizes)]
        
        # The time per claim should be relatively stable (not growing exponentially)
        max_time_per_claim = max(time_per_claim)
        min_time_per_claim = min(time_per_claim)
        
        # Allow up to 5x difference in time per claim (reasonable for caching effects, etc.)
        assert max_time_per_claim / min_time_per_claim < 5.0
    
    def test_memory_usage_stability(self):
        """Test that memory usage doesn't grow excessively."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Process multiple datasets in sequence
        for i in range(5):
            claims, fact_results, fallacies = self.generate_large_dataset(200)
            pipeline = ScoringPipeline()
            
            result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
            assert result.scoring_performed is True
            
            current_memory = process.memory_info().rss
            memory_growth = current_memory - initial_memory
            
            # Memory growth should be reasonable (less than 100MB for these tests)
            assert memory_growth < 100 * 1024 * 1024  # 100MB limit
            
            print(f"Iteration {i+1}: Memory growth: {memory_growth / (1024*1024):.1f}MB")
    
    def test_concurrent_scoring_safety(self):
        """Test that concurrent scoring operations don't interfere."""
        import threading
        import queue
        
        claims, fact_results, fallacies = self.generate_large_dataset(50)
        results_queue = queue.Queue()
        
        def score_worker():
            pipeline = ScoringPipeline()
            result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
            results_queue.put(result)
        
        # Run multiple scoring operations concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=score_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all results are valid and consistent
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        assert len(results) == 5
        
        # All results should be successful
        for result in results:
            assert result.scoring_performed is True
            assert result.debate_score.total_claims == 50
        
        # Results should be identical (deterministic scoring)
        reference_score = results[0].debate_score.overall_score
        for result in results[1:]:
            assert abs(result.debate_score.overall_score - reference_score) < 0.001
    
    def test_extreme_configurations(self):
        """Test performance with extreme configurations."""
        claims, fact_results, fallacies = self.generate_large_dataset(100)
        
        # Test with extreme weights
        extreme_configs = [
            ScoringConfig(claim_confidence_weight=1.0, fact_check_weight=0.0, fallacy_penalty_weight=0.0),
            ScoringConfig(claim_confidence_weight=0.0, fact_check_weight=1.0, fallacy_penalty_weight=0.0),
            ScoringConfig(claim_confidence_weight=0.0, fact_check_weight=0.0, fallacy_penalty_weight=1.0),
            ScoringConfig(high_confidence_threshold=0.99, medium_confidence_threshold=0.98),
            ScoringConfig(high_confidence_threshold=0.01, medium_confidence_threshold=0.001),
        ]
        
        for config in extreme_configs:
            pipeline = ScoringPipeline(config)
            
            start_time = time.time()
            result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            assert result.scoring_performed is True
            assert processing_time < 2.0  # Should still be reasonably fast
            
            # Scores should still be in valid ranges
            assert 0.0 <= result.debate_score.overall_score <= 1.0
    
    def test_repeated_scoring_consistency(self):
        """Test that repeated scoring of the same data is consistent."""
        claims, fact_results, fallacies = self.generate_large_dataset(100)
        pipeline = ScoringPipeline()
        
        scores = []
        times = []
        
        for i in range(10):
            start_time = time.time()
            result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
            end_time = time.time()
            
            scores.append(result.debate_score.overall_score)
            times.append(end_time - start_time)
            
            assert result.scoring_performed is True
        
        # All scores should be identical (deterministic)
        reference_score = scores[0]
        for score in scores:
            assert abs(score - reference_score) < 0.001
        
        # Performance should be consistent (no major degradation)
        avg_time = statistics.mean(times)
        max_time = max(times)
        min_time = min(times)
        
        # Max time should not be more than 3x the minimum (allowing for system variance)
        assert max_time / min_time < 3.0
        
        print(f"Repeated scoring - Avg: {avg_time:.4f}s, Min: {min_time:.4f}s, Max: {max_time:.4f}s")


class TestScoringStress:
    """Stress tests for extreme scenarios."""
    
    def test_empty_data_edge_cases(self):
        """Test various empty data combinations."""
        pipeline = ScoringPipeline()
        
        test_cases = [
            ([], [], []),  # All empty
            ([self._create_claim("c1")], [], []),  # Only claims
            ([], [self._create_fact_result("c1")], []),  # Only fact results (orphaned)
            ([], [], [self._create_fallacy("f1")]),  # Only fallacies
        ]
        
        for claims, fact_results, fallacies in test_cases:
            result = pipeline.score_claims_directly(claims=claims, fact_results=fact_results, fallacies=fallacies)
            
            assert result.scoring_performed is True
            assert 0.0 <= result.debate_score.overall_score <= 1.0
    
    def test_extreme_text_lengths(self):
        """Test with extremely long and short claim texts."""
        pipeline = ScoringPipeline()
        
        claims = [
            # Very short text
            Claim(
                id="short", type="factual", text="No", speaker="A", confidence=0.7,
                sentence_id="s1", turn_id=1, char_start=0, char_end=2
            ),
            # Very long text
            Claim(
                id="long", type="factual", 
                text="This is an extremely long claim " * 200,  # ~6600 characters
                speaker="B", confidence=0.7,
                sentence_id="s2", turn_id=2, char_start=3, char_end=6603
            ),
            # Empty-like text
            Claim(
                id="minimal", type="factual", text=".", speaker="C", confidence=0.7,
                sentence_id="s3", turn_id=3, char_start=6604, char_end=6605
            )
        ]
        
        result = pipeline.score_claims_directly(claims=claims)
        
        assert result.scoring_performed is True
        assert result.debate_score.total_claims == 3
        
        # Check that argument scores handle length appropriately
        for arg_score in result.debate_score.argument_scores:
            assert 0.0 <= arg_score.clarity_score <= 1.0
    
    def test_extreme_confidence_values(self):
        """Test with boundary confidence values."""
        claims = [
            Claim(
                id="zero", type="factual", text="Zero confidence", speaker="A", confidence=0.0,
                sentence_id="s1", turn_id=1, char_start=0, char_end=15
            ),
            Claim(
                id="perfect", type="factual", text="Perfect confidence", speaker="B", confidence=1.0,
                sentence_id="s2", turn_id=2, char_start=16, char_end=34
            ),
            Claim(
                id="epsilon", type="factual", text="Tiny confidence", speaker="C", confidence=0.001,
                sentence_id="s3", turn_id=3, char_start=35, char_end=50
            ),
            Claim(
                id="near_perfect", type="factual", text="Near perfect", speaker="D", confidence=0.999,
                sentence_id="s4", turn_id=4, char_start=51, char_end=63
            )
        ]
        
        pipeline = ScoringPipeline()
        result = pipeline.score_claims_directly(claims=claims)
        
        assert result.scoring_performed is True
        assert 0.0 <= result.debate_score.overall_score <= 1.0
        
        # All speakers should be scored
        assert len(result.debate_score.speaker_scores) == 4
    
    def test_massive_fallacy_count(self):
        """Test with unrealistically high fallacy counts."""
        claims = [
            Claim(
                id="c1", type="factual", text="Single claim", speaker="SPEAKER", confidence=0.7,
                sentence_id="s1", turn_id=1, char_start=0, char_end=12
            )
        ]
        
        # Create many fallacies for one speaker
        fallacies = []
        for i in range(100):  # 100 fallacies!
            fallacies.append(
                FallacyResult(
                    id=f"f{i}", type=FallacyType.AD_HOMINEM, text=f"Fallacy {i}",
                    speaker="SPEAKER", confidence=0.8, severity=FallacySeverity.HIGH
                )
            )
        
        pipeline = ScoringPipeline()
        result = pipeline.score_claims_directly(claims=claims, fallacies=fallacies)
        
        assert result.scoring_performed is True
        
        # Score should be heavily penalized but not broken
        assert 0.0 <= result.debate_score.overall_score <= 1.0
        assert result.debate_score.logical_consistency < 0.5  # Should be very low
        
        # Speaker should have terrible credibility
        speaker_score = result.debate_score.speaker_scores["SPEAKER"]
        assert speaker_score.credibility_score < 0.3
    
    def test_unicode_and_special_characters(self):
        """Test with unicode and special characters in claims."""
        claims = [
            Claim(
                id="unicode", type="factual", 
                text="Testing unicode: 中文, العربية, 🔥, ñoño, café",
                speaker="INTERNATIONAL", confidence=0.7,
                sentence_id="s1", turn_id=1, char_start=0, char_end=50
            ),
            Claim(
                id="special", type="factual",
                text="Special chars: @#$%^&*()[]{}|\\:;\"'<>?,./`~",
                speaker="SYMBOLS", confidence=0.7,
                sentence_id="s2", turn_id=2, char_start=51, char_end=95
            ),
            Claim(
                id="mixed", type="factual",
                text="Mixed: Hello 世界 🌍 @test #tag $100 50% <html>",
                speaker="MIXED", confidence=0.7,
                sentence_id="s3", turn_id=3, char_start=96, char_end=143
            )
        ]
        
        pipeline = ScoringPipeline()
        result = pipeline.score_claims_directly(claims=claims)
        
        assert result.scoring_performed is True
        assert result.debate_score.total_claims == 3
        
        # Should handle unicode gracefully
        for speaker in ["INTERNATIONAL", "SYMBOLS", "MIXED"]:
            assert speaker in result.debate_score.speaker_scores
    
    def _create_claim(self, claim_id: str) -> Claim:
        """Helper to create a simple claim."""
        return Claim(
            id=claim_id, type="factual", text="Test claim", speaker="SPEAKER", confidence=0.7,
            sentence_id="s1", turn_id=1, char_start=0, char_end=10
        )
    
    def _create_fact_result(self, claim_id: str) -> FactCheckResult:
        """Helper to create a fact check result."""
        return FactCheckResult(
            claim_id=claim_id, service_name="test", query="test", claim_text="Test claim",
            status=VerificationStatus.LIKELY_TRUE, confidence=0.8, verification_score=0.8
        )
    
    def _create_fallacy(self, fallacy_id: str) -> FallacyResult:
        """Helper to create a fallacy."""
        return FallacyResult(
            id=fallacy_id, type=FallacyType.AD_HOMINEM, text="Test fallacy",
            speaker="SPEAKER", confidence=0.7, severity=FallacySeverity.MEDIUM
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to show print statements
