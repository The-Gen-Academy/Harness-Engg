from types import SimpleNamespace

from rich.console import Console

from harness_demo.agent_loop import AgentLoop
from harness_demo.events import EventRecorder
from harness_demo.harness.policy import WritePolicy
from harness_demo.tools import ToolExecutor


class FakeModel:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def respond(self, *, input_items, instructions, tools=None, tool_choice=None):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="list_files",
                        arguments='{"path":"."}',
                        call_id="call-1",
                    )
                ],
                output_text="",
            )
        assert any(
            isinstance(item, dict) and item.get("type") == "function_call_output"
            for item in input_items
        )
        return SimpleNamespace(
            output=[SimpleNamespace(type="message")],
            output_text="Inspected the workspace.",
        )


class AlwaysToolModel:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def respond(self, *, input_items, instructions, tools=None, tool_choice=None):
        self.calls += 1
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    name="list_files",
                    arguments='{"path":"."}',
                    call_id=f"call-{self.calls}",
                )
            ],
            output_text="",
        )


def test_agent_loop_returns_tool_output_to_model(tmp_path) -> None:
    (tmp_path / "app.js").write_text("const ok = true;\n", encoding="utf-8")
    recorder = EventRecorder("agent-loop-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=3)
    model = FakeModel()
    loop = AgentLoop(model, executor, recorder, instructions="Test instructions")

    session = loop.run("Inspect the files")

    assert model.calls == 2
    assert executor.call_count == 1
    assert session.final_text == "Inspected the workspace."
    assert recorder.events[-1].data == {"summary": "Inspected the workspace."}


def test_tool_budget_stops_before_an_extra_model_call(tmp_path) -> None:
    (tmp_path / "app.js").write_text("const ok = true;\n", encoding="utf-8")
    recorder = EventRecorder("agent-loop-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=2)
    model = AlwaysToolModel()
    loop = AgentLoop(
        model,
        executor,
        recorder,
        instructions="Test instructions",
        max_model_turns=2,
    )

    session = loop.run("Attempt")

    assert model.calls == 2
    assert session.model_turns == 2
    assert session.final_text == "Tool budget exhausted for this attempt (2 calls)"


def test_agent_loop_stops_before_turn_when_deadline_expired(tmp_path) -> None:
    recorder = EventRecorder("agent-loop-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=1)
    model = AlwaysToolModel()
    loop = AgentLoop(model, executor, recorder, instructions="Test instructions")

    session = loop.run("Do work", deadline=0)

    assert model.calls == 0
    assert session.final_text == "Harness time budget exhausted before the next model turn"


def test_agent_loop_can_force_the_first_tool(tmp_path) -> None:
    class RecordingModel(FakeModel):
        def __init__(self) -> None:
            super().__init__()
            self.tool_choices = []

        def respond(self, *, input_items, instructions, tools=None, tool_choice=None):
            self.tool_choices.append(tool_choice)
            return super().respond(
                input_items=input_items,
                instructions=instructions,
                tools=tools,
                tool_choice=tool_choice,
            )

    (tmp_path / "app.js").write_text("const ok = true;\n", encoding="utf-8")
    recorder = EventRecorder("agent-loop-test", Console(file=None, quiet=True))
    executor = ToolExecutor(WritePolicy.basic(tmp_path), recorder, max_calls=3)
    model = RecordingModel()
    loop = AgentLoop(model, executor, recorder, instructions="Test instructions")

    loop.run("Inspect the files", required_first_tool="list_files")

    assert model.tool_choices[0] == {"type": "function", "name": "list_files"}
    assert model.tool_choices[1] == "auto"
