from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from harness_demo.events import EventRecorder
from harness_demo.tools import ToolExecutor


class ResponsesModel(Protocol):
    model: str

    def respond(
        self,
        *,
        input_items: list[Any],
        instructions: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, str] | None = None,
    ) -> Any: ...


@dataclass
class AgentSession:
    history: list[Any] = field(default_factory=list)
    final_text: str = ""
    model_turns: int = 0


class AgentLoop:
    def __init__(
        self,
        model: ResponsesModel,
        tools: ToolExecutor,
        recorder: EventRecorder,
        *,
        instructions: str,
        max_model_turns: int = 12,
    ) -> None:
        self.model = model
        self.tools = tools
        self.recorder = recorder
        self.instructions = instructions
        self.max_model_turns = max_model_turns

    def run(
        self,
        user_message: str,
        session: AgentSession | None = None,
        *,
        deadline: float | None = None,
        required_first_tool: str | None = None,
    ) -> AgentSession:
        session = session or AgentSession()
        session.history.append({"role": "user", "content": user_message})
        turns_this_attempt = 0

        while turns_this_attempt < self.max_model_turns:
            if deadline is not None and time.monotonic() >= deadline:
                message = "Harness time budget exhausted before the next model turn"
                self.recorder.emit("guardrail", message, status="failure")
                session.final_text = message
                return session
            if self.tools.call_count >= self.tools.max_calls:
                message = f"Tool budget exhausted for this attempt ({self.tools.max_calls} calls)"
                self.recorder.emit("guardrail", message, status="failure")
                session.final_text = message
                return session
            tool_choice: str | dict[str, str] = "auto"
            if turns_this_attempt == 0 and required_first_tool:
                tool_choice = {"type": "function", "name": required_first_tool}
            response = self.model.respond(
                input_items=session.history,
                instructions=self.instructions,
                tools=self.tools.schemas,
                tool_choice=tool_choice,
            )
            session.model_turns += 1
            turns_this_attempt += 1
            session.history.extend(response.output)
            function_calls = [item for item in response.output if item.type == "function_call"]

            if not function_calls:
                session.final_text = (response.output_text or "").strip()
                self.recorder.emit(
                    "agent",
                    "Returned a final work summary",
                    status="success",
                    data={"summary": session.final_text},
                )
                return session

            for call in function_calls:
                result = self.tools.call(call.name, call.arguments)
                session.history.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result,
                    }
                )

        if self.tools.call_count >= self.tools.max_calls:
            message = f"Tool budget exhausted for this attempt ({self.tools.max_calls} calls)"
        else:
            message = f"Model turn budget exhausted for this attempt ({self.max_model_turns} turns)"
        self.recorder.emit("guardrail", message, status="failure")
        session.final_text = message
        return session
