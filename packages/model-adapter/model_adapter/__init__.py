"""Public surface of the model adapter.

The orchestrator and tests import from this module only. Provider implementations
are internal detail.
"""

from model_adapter.client import ModelClient
from model_adapter.config import ModelSettings
from model_adapter.factory import get_client
from model_adapter.routing import RoutingClient
from model_adapter.types import (
    ModelMessage,
    ModelResponse,
    StreamChunk,
    TaskClass,
    ToolCall,
    ToolSpec,
    Usage,
)

__all__ = [
    "ModelClient",
    "ModelMessage",
    "ModelResponse",
    "ModelSettings",
    "RoutingClient",
    "StreamChunk",
    "TaskClass",
    "ToolCall",
    "ToolSpec",
    "Usage",
    "get_client",
]
