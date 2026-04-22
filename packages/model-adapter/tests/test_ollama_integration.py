"""Integration test against a real local Ollama. Skip if unreachable.

Run with: pytest -m integration
"""

from __future__ import annotations

import os

import httpx
import pytest

from model_adapter import ModelMessage, ToolSpec
from model_adapter.providers.ollama import OllamaProvider

pytestmark = pytest.mark.integration


OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
INTEGRATION_MODEL = os.environ.get("INTEGRATION_MODEL", "llama3.2:3b")


def _ollama_up() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


skip_if_down = pytest.mark.skipif(not _ollama_up(), reason="Ollama not reachable")


@skip_if_down
async def test_real_tool_call():
    """Sanity: a real local model should respond to a tool-enabled prompt."""
    provider = OllamaProvider(base_url=OLLAMA_BASE, default_model=INTEGRATION_MODEL)
    tool = ToolSpec(
        name="echo",
        description="Echo back the input string.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )
    resp = await provider.complete(
        messages=[
            ModelMessage(role="system", content="When the user says hi, call the echo tool."),
            ModelMessage(role="user", content="Say hi by calling echo with text='hi'."),
        ],
        tools=[tool],
        temperature=0.0,
    )
    # We don't require the model to call the tool — some small models miss it.
    # We DO require the call to succeed and return a parseable response.
    assert resp.finish_reason in ("stop", "tool_calls")
