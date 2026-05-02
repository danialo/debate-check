from pathlib import Path

from debate_claim_extractor.core import heuristics


def test_sentence_tokenise_handles_run_on_transcript():
    text = Path("tests/transcripts/2.txt").read_text()
    spans = heuristics.sentence_tokenise(text)

    assert len(spans) > 20
    assert max(len(sentence.split()) for sentence, *_ in spans) <= 50
