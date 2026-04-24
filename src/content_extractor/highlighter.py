import re


def highlight_occurrence(text: str, keyword: str) -> str:
    if not keyword or not text:
        return text

    escaped_keyword = re.escape(keyword)

    pattern = re.compile(f"({escaped_keyword})", re.IGNORECASE)

    highlighted = pattern.sub(r'<span class="occurrence">\1</span>', text, count=1)

    return highlighted
