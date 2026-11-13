"""Kam šel čas jedné dávky srdce: rozpad kroků z deníku dávek na fáze (docs/navrhy/2026-11-13-pruhled-srdce.md §2).

Krok je `{t, kind, text}` (`backend/brain_opora/heart/steps.py`): `tool` je volání nástroje, `result` jeho výsledek
(v pořadí volání), `text`/`thinking` řeč modelu. Čas mezi kroky patří nejstaršímu otevřenému nástroji, a když žádný
není otevřený, modelu (přemýšlí, píše, ptá se poradce). Je to odhad z časů kroků, ne měření uvnitř nástroje.
"""
import re

# Podpříkazy `opora_heart.py`, které jen čtou; ostatní zapisují do OPORY (plán, kroky, odpovědi, rozhodnutí).
HEART_READS = {"ctx", "snapshot", "skill", "canvas", "show", "ls", "plan-of", "research-map"}
PHASES = {
    "model": "model přemýšlí a píše (vč. poradce)",
    "opora_read": "čtení podkladů z OPORY",
    "opora_write": "zápis do OPORY (čeká na server)",
    "files": "čtení kódu a souborů",
    "write_files": "příprava souborů",
    "commands": "jiné příkazy",
    "agents": "podagenti",
}
HEART_CMD = re.compile(r"opora_heart\.py\s+([\w-]+)")
CODE = re.compile(r'"code":\s*"([\w.-]+)"')


def category(tool_text):
    name, _, body = tool_text.partition(":")
    if name == "Bash":
        found = HEART_CMD.search(body)
        if found:
            return "opora_read" if found.group(1) in HEART_READS else "opora_write"
        return "commands"
    if name in ("Read", "Glob", "Grep", "LS", "WebFetch", "WebSearch"):
        return "files"
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return "write_files"
    if name in ("Agent", "Task"):
        return "agents"
    return "commands"


def _short(tool_text):
    found = HEART_CMD.search(tool_text)
    return f"opora_heart.py {found.group(1)}" if found else tool_text.split(",")[0][:80]


def analyze(batch):
    """`{phases: [{id, label, ms, share}], tools: [{tool, ms, failed}], slowest, failures, truncated, untracedMs}`."""
    steps = [step for step in batch.get("steps") or [] if isinstance(step, dict) and isinstance(step.get("t"), int)]
    end = batch.get("durationMs") if isinstance(batch.get("durationMs"), int) else (steps[-1]["t"] if steps else 0)
    totals, open_tools, calls = dict.fromkeys(PHASES, 0), [], []
    last = 0
    for step in steps:
        span = max(step["t"] - last, 0)
        totals[open_tools[0]["category"] if open_tools else "model"] += span
        last = max(last, step["t"])
        if step["kind"] == "tool":
            call = {"tool": _short(step["text"]), "category": category(step["text"]), "start": step["t"],
                    "ms": None, "failed": None}
            open_tools.append(call)
            calls.append(call)
        elif step["kind"] == "result" and open_tools:
            call = open_tools.pop(0)
            call["ms"] = step["t"] - call["start"]
            text = step.get("text") or ""
            if text.startswith("Exit code") or '"error"' in text[:200]:
                code = CODE.search(text)
                call["failed"] = code.group(1) if code else text[:120]
    totals[open_tools[0]["category"] if open_tools else "model"] += max(end - last, 0)
    whole = sum(totals.values()) or 1
    phases = [{"id": key, "label": PHASES[key], "ms": ms, "share": round(ms / whole, 2)}
              for key, ms in sorted(totals.items(), key=lambda item: -item[1]) if ms]
    timed = [call for call in calls if call["ms"] is not None]
    return {
        "phases": phases,
        "slowest": [{"tool": c["tool"], "ms": c["ms"], "category": c["category"]}
                    for c in sorted(timed, key=lambda c: -c["ms"])[:5]],
        "failures": [{"tool": c["tool"], "error": c["failed"], "ms": c["ms"]} for c in calls if c["failed"]],
        "unanswered": [c["tool"] for c in calls if c["ms"] is None],
        "truncated": len(steps) >= 80,  # steps.MAX_STEPS: konec dávky v deníku chybí
        "durationMs": end,
    }


def headline(analysis):
    """Jedna věta pro agenta i člověka: dvě největší fáze a selhání."""
    top = [f"{phase['label']} {round(phase['ms'] / 1000)} s" for phase in analysis["phases"][:2]]
    if not top:
        return "Dávka bez kroků."
    sentence = f"Dávka {round(analysis['durationMs'] / 1000)} s: " + ", ".join(top)
    if analysis["failures"]:
        sentence += f"; selhalo {len(analysis['failures'])}× (" + ", ".join(
            f"{item['tool']}: {item['error']}" for item in analysis["failures"][:3]) + ")"
    return sentence + "."

