from debate_claim_extractor.core.normalize import needs_normalisation, normalise_blocks


def test_needs_normalisation_detects_run_on_block():
    block = "Charles I want to compare notes on free will one of my favorite things here is my take we can observe causality as absolutely true given initial conditions"
    assert needs_normalisation(block) is True


def test_normalise_blocks_splits_long_section():
    block = (
        "Charles I want to compare notes on free will it is true that at some level of resolution causality is absolutely true given these initial conditions this is what will"
        " happen afterwards the physicist speaking so if you take it to its logical conclusion then there is no free will because everything is predetermined"
    )
    chunks = normalise_blocks([block])
    assert len(chunks) >= 2
    assert all(len(chunk.split()) <= 35 for chunk in chunks)

