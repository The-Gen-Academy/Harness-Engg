from dataclasses import dataclass

from harness_demo.harness.evaluator import Evaluation


@dataclass(frozen=True)
class CompletionDecision:
    approved: bool
    message: str


def decide_completion(
    evaluation: Evaluation, revision: int, max_revisions: int
) -> CompletionDecision:
    if evaluation.approved:
        return CompletionDecision(True, "Approved by the external completion gate")
    if revision < max_revisions:
        return CompletionDecision(False, f"Revision required ({revision + 1}/{max_revisions})")
    return CompletionDecision(False, f"Not approved after {max_revisions} revisions")
