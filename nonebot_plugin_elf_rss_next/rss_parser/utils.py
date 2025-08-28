import re
from typing import Any


def get_summary(entry: dict[str, Any]) -> str:
    summary: str = (
        entry["content"][0]["value"] if entry.get("content") else entry["summary"]
    )
    return f"<div>{summary}</div>" if re.search(r"^https?://", summary) else summary
