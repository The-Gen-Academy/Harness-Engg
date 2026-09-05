from types import SimpleNamespace

from harness_demo.model import DEFAULT_MODEL, OpenAIResponsesModel


def test_demo_defaults_to_pinned_mini_snapshot() -> None:
    assert DEFAULT_MODEL == "gpt-4o-mini-2024-07-18"


def test_model_uses_deterministic_sampling_and_forced_tool_choice() -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        @staticmethod
        def create(**request):
            captured.update(request)
            return SimpleNamespace(output=[])

    model = OpenAIResponsesModel.__new__(OpenAIResponsesModel)
    model.model = DEFAULT_MODEL
    model.client = SimpleNamespace(responses=FakeResponses())
    forced = {"type": "function", "name": "submit_candidate"}

    model.respond(
        input_items=[{"role": "user", "content": "Fix it"}],
        instructions="Use tools",
        tools=[{"type": "function", "name": "submit_candidate"}],
        tool_choice=forced,
    )

    assert captured["model"] == DEFAULT_MODEL
    assert captured["temperature"] == 0
    assert captured["tool_choice"] == forced
    assert captured["parallel_tool_calls"] is False
