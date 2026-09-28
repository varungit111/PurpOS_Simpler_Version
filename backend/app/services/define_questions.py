_QUESTION_LABELS = {
    "pestle_findings": "Review relevant PESTLE findings.",
    "social_contribution_evidence": (
        "What evidence demonstrates the organisation's social contribution?"
    ),
    "vulnerabilities_gaps": (
        "What important vulnerabilities or evidence gaps remain?"
    ),
    "evidence_references": (
        "Which evidence sources should be carried forward and verified?"
    ),
}


def deduplicate_define_questions(questions: list[str]) -> list[str]:
    """Remove exact duplicates while retaining first-seen order."""
    return list(dict.fromkeys(questions))


def present_define_questions(questions: list[str]) -> list[str]:
    """Make known methodology keys readable without changing stored questions."""
    return [_QUESTION_LABELS.get(question, question) for question in questions]
