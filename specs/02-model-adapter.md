# 02 — Model Adapter

## Goal
A single Python interface that the orchestrator calls. Behind it, we can swap Ollama, OpenAI, Anthropic, or vLLM without touching orchestration code. This is the most important abstraction in the project — get it right and the local-vs-paid decision becomes a config flag forever.

## Location
`packages/model-adapter/`

## Public Interface
```python
# packages/model-adapter/model_adapter/client.py

from typing import AsyncIterator, Literal
from pydantic import BaseModel

class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list["ToolCall"] | None = None
    tool_call_id: str | None = None

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict

class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict  # JSON Schema

class ModelResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall]
    finish_reason: Literal["stop", "tool_calls", "length", "error"]
    usage: "Usage"

class Usage(BaseModel):
    input_tokens: int
    output_tokens: int

class StreamChunk(BaseModel):
    type: Literal["text", "tool_call_start", "tool_call_delta", "tool_call_end", "done"]
    content: str | None = None
    tool_call: ToolCall | None = None

class ModelClient:
    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,  # override default
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ModelResponse: ...

    async def stream(
        self,
        messages: list[ModelMessage],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]: ...
```

## Provider Implementations
Three providers in v1, each in its own module:
- `model_adapter/providers/ollama.py` — uses `langchain-ollama` or direct httpx to `http://localhost:11434`
- `model_adapter/providers/openai_compat.py` — works for OpenAI, vLLM, any OpenAI-API-compatible server
- `model_adapter/providers/anthropic.py` — for the eventual Claude path; stub OK in PoC but the file must exist

A factory `get_client(provider: str) -> ModelClient` reads `MODEL_PROVIDER` env var.

## Routing
Add a `RoutingClient` that wraps the base client and picks a model based on a task classification. The classification is itself a model call to a small fast model.

```python
class TaskClass(str, Enum):
    CLASSIFY = "classify"   # routing decisions, intent detection
    REASON = "reason"       # general agent steps
    HEAVY = "heavy"         # planning, complex tool selection

# Config maps each class to a model name
TASK_MODEL_MAP = {
    TaskClass.CLASSIFY: "llama3.2:3b",
    TaskClass.REASON: "qwen2.5:14b",
    TaskClass.HEAVY: "qwen2.5:32b",
}
```

The orchestrator passes a `task_class` hint per call. If absent, default to `REASON`.

## Tool-Calling Normalization
Local models return tool calls in inconsistent formats. The Ollama provider must:
1. Try native tool calling first (`/api/chat` with `tools` parameter).
2. Fall back to JSON-mode prompting if the model doesn't support native tools.
3. Always normalize the output to the `ToolCall` schema above.

Document which models you've tested and their tool-call mode in `packages/model-adapter/COMPATIBILITY.md`.

## Configuration
Env vars (loaded via `pydantic-settings`):
```
MODEL_PROVIDER=ollama        # ollama | openai_compat | anthropic
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_BASE_URL=             # for vLLM/OpenAI
OPENAI_API_KEY=              # required when provider != ollama
ANTHROPIC_API_KEY=
DEFAULT_MODEL=qwen2.5:14b
ROUTER_MODEL=llama3.2:3b
HEAVY_MODEL=qwen2.5:32b
```

## Acceptance Criteria
- [ ] `ModelClient` interface defined and documented.
- [ ] All three providers implement the interface; Anthropic can raise `NotImplementedError` on `complete` but the file/class must exist.
- [ ] `pytest` suite covers: a happy-path complete call, a streaming call, a tool-call response, and an error case (mocked HTTP failures).
- [ ] Integration test (skip-if-Ollama-unavailable) hits a real Ollama instance and successfully calls a tool.
- [ ] Switching providers requires only changing `MODEL_PROVIDER` env var; no code changes.
- [ ] No orchestration code anywhere imports `langchain_ollama`, `openai`, or `anthropic` directly. They only import from `model_adapter`.

## Anti-Goals
- Don't build a feature-complete LiteLLM clone. Only support what the orchestrator needs.
- Don't expose provider-specific kwargs through the interface. If something is provider-specific, it goes in env config.
