"""Mocked-HTTP tests for the OpenAI-compat provider."""

from __future__ import annotations

import json

import httpx
import pytest

from model_adapter import ModelMessage, ToolSpec
from model_adapter.providers import openai_compat as openai_mod
from model_adapter.providers.openai_compat import OpenAICompatProvider


@pytest.fixture
def provider() -> OpenAICompatProvider:
    return OpenAICompatProvider(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        default_model="gpt-4o-mini",
    )


def _install_transport(monkeypatch, handler):
    RealAsyncClient = httpx.AsyncClient

    class PatchedAsyncClient(RealAsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(openai_mod.httpx, "AsyncClient", PatchedAsyncClient)


async def test_complete_happy_path(provider, monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 8, "completion_tokens": 3},
            },
        )

    _install_transport(monkeypatch, handler)

    resp = await provider.complete(messages=[ModelMessage(role="user", content="hi")])
    assert resp.content == "hello"
    assert resp.finish_reason == "stop"
    assert resp.usage.input_tokens == 8
    assert captured["auth"] == "Bearer sk-test"
    assert captured["url"].endswith("/chat/completions")


async def test_tool_call_parses_json_arguments_string(provider, monkeypatch):
    tool = ToolSpec(name="web.fetch", description="fetch URL", parameters={"type": "object"})

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "web.fetch",
                                        "arguments": '{"url":"https://x.test"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {},
            },
        )

    _install_transport(monkeypatch, handler)

    resp = await provider.complete(
        messages=[ModelMessage(role="user", content="fetch x")],
        tools=[tool],
    )
    assert resp.finish_reason == "tool_calls"
    assert resp.tool_calls[0].id == "call_abc"
    assert resp.tool_calls[0].arguments == {"url": "https://x.test"}


async def test_http_error(provider, monkeypatch):
    def handler(request):
        return httpx.Response(429, text="rate limited")

    _install_transport(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete(messages=[ModelMessage(role="user", content="hi")])
