from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from harness_demo.paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = "gpt-4o-mini-2024-07-18"


class OpenAIResponsesModel:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("HARNESS_DEMO_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(timeout=30.0)

    def respond(
        self,
        *,
        input_items: list[Any],
        instructions: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, str] | None = None,
    ) -> Any:
        request: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": input_items,
            "temperature": 0,
        }
        if tools:
            request.update(
                {
                    "tools": tools,
                    "tool_choice": tool_choice or "auto",
                    "parallel_tool_calls": False,
                }
            )
        return self.client.responses.create(**request)
