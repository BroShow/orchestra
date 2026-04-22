# Model Compatibility

Which local models we've tested for tool-calling reliability against the Ollama provider.

| Model | Tool-calling | Notes |
|-------|--------------|-------|
| `qwen2.5:14b` | Native | Primary default. Reliable native tool calls via `/api/chat`. |
| `qwen2.5:32b` | Native | Heavier reasoning path. Same native-tool behavior as 14b. |
| `llama3.2:3b` | Native (limited) | Router/classifier only. Keep it to single-step classification calls. |
| `llama3.1:70b` | Native | Alternative heavy model if 64GB+ RAM. |

When adding a new model, smoke-test it with the integration tests under `tests/test_ollama_integration.py` before relying on it in production paths. If native tool-calling is unreliable for a model, wrap it in a JSON-mode prompt fallback inside `OllamaProvider._build_body`.
