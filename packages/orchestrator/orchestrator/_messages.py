"""Convert between LangChain BaseMessage (used in AgentState) and ModelMessage
(used by the model adapter). Keeps both layers independent."""

from __future__ import annotations

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from model_adapter import ModelMessage, ToolCall


def to_model_messages(messages: list[BaseMessage]) -> list[ModelMessage]:
    out: list[ModelMessage] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            out.append(ModelMessage(role="system", content=_as_text(m.content)))
        elif isinstance(m, HumanMessage):
            out.append(ModelMessage(role="user", content=_as_text(m.content)))
        elif isinstance(m, AIMessage):
            tool_calls = None
            if m.tool_calls:
                tool_calls = [
                    ToolCall(id=tc["id"], name=tc["name"], arguments=tc.get("args") or {})
                    for tc in m.tool_calls
                ]
            out.append(
                ModelMessage(
                    role="assistant",
                    content=_as_text(m.content) or "",
                    tool_calls=tool_calls,
                )
            )
        elif isinstance(m, ToolMessage):
            out.append(
                ModelMessage(
                    role="tool",
                    content=_as_text(m.content),
                    tool_call_id=m.tool_call_id,
                )
            )
        else:
            out.append(ModelMessage(role="user", content=_as_text(m.content)))
    return out


def _as_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # list-of-blocks format (langchain structured content)
        parts: list[str] = []
        for c in content:
            if isinstance(c, dict):
                parts.append(c.get("text", ""))
            else:
                parts.append(str(c))
        return "".join(parts)
    return str(content)


def ai_message_from_response(content: str, tool_calls: list[ToolCall]) -> AIMessage:
    """Build a LangChain AIMessage from our adapter's ModelResponse."""
    lc_tool_calls = [
        {"id": tc.id, "name": tc.name, "args": tc.arguments, "type": "tool_call"}
        for tc in tool_calls
    ]
    return AIMessage(content=content, tool_calls=lc_tool_calls)
