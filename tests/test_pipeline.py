from __future__ import annotations

from debate_claim_extractor import ClaimExtractionPipeline, ExtractionConfig
from debate_claim_extractor.core.llm import LLMClaim, StaticLLMClient

SAMPLE_DEBATE = """
MODERATOR: Welcome to tonight's debate on economic policy.

CANDIDATE A: Unemployment has decreased by 15% over the last year due to our economic policies.

CANDIDATE B: That statistic is misleading because it doesn't account for underemployment. In 2008, we saw similar patterns during the financial crisis.

CANDIDATE A: My plan is better than my opponent's plan because it creates more jobs and reduces the deficit.

CANDIDATE B: Moreover, my opponent's plan will increase costs due to higher taxes needed to fund the system.
"""

UNLABELED_DEBATE = """
Welcome to tonight's debate on economic policy. Unemployment has decreased by 15% over the last year due to our economic policies.

That statistic is misleading because it doesn't account for underemployment. In 2008, we saw similar patterns during the financial crisis.

My plan is better than my opponent's plan because it creates more jobs and reduces the deficit.

Moreover, my opponent's plan will increase costs due to higher taxes needed to fund the system.
"""


def test_heuristic_pipeline_basic():
    pipeline = ClaimExtractionPipeline()
    result = pipeline.extract(SAMPLE_DEBATE)

    summaries = {claim.claim_type: claim.text for claim in result.claims}

    assert any("15%" in claim.text for claim in result.claims)
    assert any("2008" in claim.text for claim in result.claims)
    assert any("better than" in claim.text for claim in result.claims)
    assert result.diagnostics["heuristic_candidates"] == len(result.claims)


def test_llm_integration_adds_claims():
    client = StaticLLMClient({
        "My opponent's plan will increase costs due to higher taxes": [
            LLMClaim(
                text="My opponent's plan raises taxes on middle-class families",
                claim_type="factual",
                confidence=0.95,
            )
        ]
    })

    pipeline = ClaimExtractionPipeline(ExtractionConfig(use_llm=True, llm_client=client))
    result = pipeline.extract(SAMPLE_DEBATE)

    assert any("middle-class families" in claim.text for claim in result.claims)
    assert result.diagnostics["llm_candidates"] >= 1


def test_unlabeled_transcript_processed():
    pipeline = ClaimExtractionPipeline()
    result = pipeline.extract(UNLABELED_DEBATE)

    assert result.diagnostics["utterances"] >= 1
    assert any("15%" in claim.text for claim in result.claims)
