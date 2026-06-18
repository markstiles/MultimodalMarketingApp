import logging
import re

logger = logging.getLogger(__name__)

_PATTERNS: dict[str, list[str]] = {
    "politics": [r"\bpoliti", r"\belection\b", r"\bvote\b", r"\bcongress\b", r"\bsenate\b"],
    "medical": [r"\bdiagnos", r"\bmedical\b", r"\bdoctor\b", r"\bprescri", r"\bsymptom"],
    "legal": [r"\blawsuit\b", r"\blegal advice\b", r"\battorney\b", r"\blitigat"],
    "gambling": [r"\bcasino\b", r"\bgambl", r"\bbetting\b", r"\bodds\b"],
    "personal": [r"\btherapy\b", r"\bdepression\b", r"\banxiety\b", r"\bsuicid"],
}


def classify_message(message: str) -> str | None:
    """Return the first matched category, or None if none match. Does NOT block."""
    lower = message.lower()
    for category, patterns in _PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower):
                logger.info("guardrail_category_detected category=%s", category)
                return category
    return None
