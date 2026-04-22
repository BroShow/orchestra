"""Mocked-HTTP tests for the Ollama provider.

Uses httpx.MockTransport so responses carry their request context (needed for
raise_for_status) and the provider's own AsyncClient plumbing is exercised.
"""

from __future__ import annotations

import json

import httpx
import pytest

from model_adapter import ModelMessage, ToolSpec
from model_adapter.providers import ollama as ollama_mod
from model_adapter.providers.ollama import OllamaProvider


@pytest.fixture
def provider() -> OllamaProvider:
    return OllamaProvider(base_url="http://ollama.local", default_model="qwen2.5:14b")


def _install_transport(monkeypatch, handler):
    """Patch httpx.AsyncClient so the provider's `async with httpx.AsyncClient(...)`
    uses a MockTransport-backed client.
    """
    RealAsyncClient = httpx.AsyncClient

    class PatchedAsyncClient(RealAsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ollama_mod.httpx, "AsyncClient", PatchedAsyncClient)


async def test_complete_happy_path(provider, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "qwen2.5:14b"
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "hi there"},
                "done": True,
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )

    _install_transport(monkeypatch, handler)

    resp = await provider.complete(messages=[ModelMessage(role="user", content="hello")])
    assert resp.content == "hi there"
    assert resp.tool_calls == []
    assert resp.finish_reason == "stop"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 5


async def test_complete_with_tool_call(provider, monkeypatch):
    tool = ToolSpec(
        name="fs.read_file",
        description="Read a file",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["tools"][0]["function"]["name"] == "fs.read_file"
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "fs.read_file", "arguments": {"path": "x.txt"}}}
                    ],
                },
                "done": True,
            },
        )

    _install_transport(monkeypatch, handler)

    resp = await provider.complete(
        messages=[ModelMessage(role="user", content="read x.txt")],
        tools=[tool],
    )
    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.name == "fs.read_file"
    assert tc.arguments == {"path": "x.txt"}
    assert tc.id


async def test_complete_tool_args_as_json_string(provider, monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "fs.read_file", "arguments": '{"path":"y.txt"}'}}
                    ],
                },
                "done": True,
            },
        )

    _install_transport(monkeypatch, handler)

    resp = await provider.complete(messages=[ModelMessage(role="user", content="ok")])
    assert resp.tool_calls[0].arguments == {"path": "y.txt"}


async def test_complete_http_error(provider, monkeypatch):
    def handler(request):
        return httpx.Response(500, text="boom")

    _install_transport(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete(messages=[ModelMessage(role="user", content="x")])


async def test_stream(provider, monkeypatch):
    chunks = [
        json.dumps({"message": {"content": "hel"}, "done": False}) + "\n",
        json.dumps({"message": {"content": "lo"}, "done": False}) + "\n",
        json.dumps({"message": {"content": ""}, "done": True}) + "\n",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = "".join(chunks).encode()
        return httpx.Response(200, content=body)

    _install_transport(monkeypatch, handler)

    out = []
    async for c in provider.stream(messages=[ModelMessage(role="user", content="hi")]):
        out.append(c)

    text = "".join(c.content or "" for c in out if c.type == "text")
    assert text == "hello"
    assert out[-1].type == "done"
