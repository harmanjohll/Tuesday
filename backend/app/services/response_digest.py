"""Clean Claude's text responses for natural speech synthesis."""

import re

# Month abbreviations -> full names
MONTH_MAP = {
    "Jan": "January", "Feb": "February", "Mar": "March",
    "Apr": "April", "Jun": "June", "Jul": "July",
    "Aug": "August", "Sep": "September", "Oct": "October",
    "Nov": "November", "Dec": "December",
}

# Day abbreviations
DAY_MAP = {
    "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
    "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday",
}


def digest_for_speech(text: str, max_length: int = 600) -> str:
    """Transform text for natural speech output.

    Strips markdown, expands abbreviations, replaces URLs,
    and truncates at a sentence boundary for TTS quota savings.
    """
    # Strip markdown headers
    text = re.sub(r"#{1,6}\s*", "", text)

    # Strip bold/italic markers
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)

    # Strip inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove code blocks entirely
    text = re.sub(r"```[\s\S]*?```", " ", text)

    # Replace URLs with domain mention
    text = re.sub(
        r"https?://(?:www\.)?([^/\s]+)[^\s]*",
        r"link to \1",
        text,
    )

    # Strip markdown list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Strip markdown table separators
    text = re.sub(r"^\s*\|[-:| ]+\|\s*$", "", text, flags=re.MULTILINE)
    # Strip table pipes
    text = re.sub(r"\|", ", ", text)

    # Expand month abbreviations (word boundary)
    for abbr, full in MONTH_MAP.items():
        text = re.sub(rf"\b{abbr}\b\.?", full, text)

    # Expand day abbreviations
    for abbr, full in DAY_MAP.items():
        text = re.sub(rf"\b{abbr}\b\.?", full, text)

    # Common abbreviations
    text = re.sub(r"\be\.g\.\s*", "for example ", text)
    text = re.sub(r"\bi\.e\.\s*", "that is ", text)
    text = re.sub(r"\betc\.\s*", "and so on ", text)
    text = re.sub(r"\bvs\.\s*", "versus ", text)

    # Star counts: "42★" -> "42 stars"
    text = re.sub(r"(\d+)★", r"\1 stars", text)

    # Collapse multiple newlines into sentence breaks
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)

    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)

    # Truncate for TTS quota and listener attention
    if len(text) > max_length:
        truncated = text[:max_length]
        last_period = truncated.rfind(".")
        if last_period > max_length * 0.5:
            text = truncated[: last_period + 1]
        else:
            text = truncated.rstrip() + "."

    return text.strip()
