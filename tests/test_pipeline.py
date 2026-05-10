"""
Integration Test — test_pipeline.py

End-to-End benchmark for the TrueBrief Pipeline.
"""

import pytest
import time
from truebrief.pipeline.runner import PipelineRunner

# Minimal set of diverse prompts for CI/CD or basic testing
TEST_PROMPTS = [
    "TSMC semiconductor manufacturing",
    "OpenAI GPT-5 release",
    "SpaceX Starship launch",
]

@pytest.mark.asyncio
async def test_end_to_end_pipeline():
    """
    Smoke test the entire pipeline on a single topic to ensure no crashes.
    """
    runner = PipelineRunner()
    
    start = time.time()
    brief = runner.run("Nvidia AI chips")
    end = time.time()
    
    assert brief is not None
    assert isinstance(brief, str)
    assert len(brief) > 50
    assert "📋 TrueBrief" in brief
    
    print(f"Pipeline took {end - start:.2f} seconds.")
    print(brief)

# Note: Full master benchmark (21 prompts) should be run manually via a script
# rather than as a standard pytest, to avoid rate limits and API costs during CI.
