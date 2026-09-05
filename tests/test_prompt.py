from harness_demo.prompt import load_task_prompt


def test_shared_prompt_is_single_source_of_truth() -> None:
    prompt = load_task_prompt()

    assert "BUILD20" in prompt
    assert "$64.00" in prompt
    assert "tool" not in prompt.casefold()
    assert "harness" not in prompt.casefold()
