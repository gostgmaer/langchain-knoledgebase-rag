"""
A real call to the configured LLM provider — opt-in only
(`pytest -m live`), since the default `addopts = "-m 'not live'"`
(pyproject.toml) excludes it from every normal run: it costs real
API quota and was previously a bare top-level `asyncio.run()` script
that fired on collection alone, before pytest even ran a single test.
"""

import pytest
from langchain_core.messages import HumanMessage

from packages.infrastructure.ai import LLMManager

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_llm_manager_returns_a_real_response():
    llm = LLMManager()

    response = await llm.ainvoke([HumanMessage(content="Say hello in exactly one sentence.")])

    assert response.content
    assert isinstance(response.content, (str, list))
