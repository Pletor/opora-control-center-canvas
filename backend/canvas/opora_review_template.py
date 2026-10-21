"""PR description sections required by the PR template (docs/oporahub-review-jobs.md, "Šablona PR").

A section counts only when a Markdown heading with its name (case-insensitive, any level) is
followed by real text before the next heading. HTML comments (the template's hints), empty
checkboxes and whitespace are not text, so an unfilled template stays incomplete. Pure."""
import re

HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
EMPTY_LINE = re.compile(r"^\s*(?:[-*+]\s*(?:\[\s?\])?\s*|>\s*)?$")
MAX_BODY, MAX_SECTIONS = 65_536, 50


def normalize(name):
    return " ".join(name.split()).casefold()


def filled_sections(body):
    """Normalized names of headings that have content, in order of appearance (bounded)."""
    if not isinstance(body, str):
        return []
    text = COMMENT.sub("", body[:MAX_BODY])
    filled, current, has_text = [], None, False
    for line in text.splitlines() + ["# end"]:
        match = HEADING.match(line)
        if match is None:
            has_text = has_text or EMPTY_LINE.match(line) is None
            continue
        if current is not None and has_text and current not in filled:
            filled.append(current)
        current, has_text = normalize(match.group(1)), False
    return filled[:MAX_SECTIONS]


def missing_sections(filled, required):
    present = set(filled)
    return [name for name in required if normalize(name) not in present]
