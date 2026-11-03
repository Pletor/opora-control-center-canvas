"""Uzel `critic`: druhý názor ChatGPT přes `codex exec` pod předplatným (kontrakt docs/navrhy/2026-11-03-novy-zaklad.md
§3, PR 9).

Vstup `{subject, criteria, context?}` (chybějící klíče doplní `params` uzlu), výstup
`{verdict: ok|concerns|reject, findings: [{severity: high|medium|low, text}], raw?}`.
Sandbox codexu na Windows soubory nečte, proto posuzovaný obsah jde celý v promptu (stdin) a codex běží `read-only`.
Uzel nikdy neselže kvůli kritikovi: chybějící codex, chyba, limit i výstup bez JSON dají `verdict: concerns`.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT = 300.0
VERDICTS = ("ok", "concerns", "reject")
SEVERITIES = ("high", "medium", "low")
RAW_LIMIT = 4000
INPUT_SCHEMA = {"type": "object", "required": ["subject"], "properties": {
    "subject": {"type": "string"}, "criteria": {"type": "array", "items": {"type": "string"}},
    "context": {"type": "string"}}}
OUTPUT_SCHEMA = {"type": "object", "required": ["verdict", "findings"], "properties": {
    "verdict": {"enum": list(VERDICTS)},
    "findings": {"type": "array", "items": {"type": "object", "properties": {
        "severity": {"enum": list(SEVERITIES)}, "text": {"type": "string"}}}},
    "raw": {"type": "string"}}}

PROMPT = """Jsi nezávislý kritik. Posuď předmět níže podle kritérií. Nic nespouštěj a nic nezapisuj.
Odpověz POUZE jedním JSON objektem přesně v tomto tvaru, bez dalšího textu:
{{"verdict": "ok" | "concerns" | "reject", "findings": [{{"severity": "high" | "medium" | "low", "text": "..."}}]}}

Kritéria:
{criteria}
{context}
Předmět:
<<<
{subject}
>>>
"""


def timeout():
    return float(os.environ.get("OPORA_CRITIC_TIMEOUT") or DEFAULT_TIMEOUT)


def build_prompt(subject, criteria, context=None):
    lines = "\n".join(f"- {item}" for item in criteria) or "- celková správnost a rizika"
    extra = f"\nKontext:\n<<<\n{context}\n>>>\n" if context else ""
    return PROMPT.format(criteria=lines, context=extra, subject=subject)


def concerns(text, raw=None):
    output = {"verdict": "concerns", "findings": [{"severity": "medium", "text": text}]}
    return {**output, "raw": raw[:RAW_LIMIT]} if raw else output


def parse(text):
    """První JSON objekt ve výstupu s platným `verdict`; nálezy s neznámou závažností dostanou `medium`."""
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text, start)
        except ValueError:
            value = None
        if isinstance(value, dict) and value.get("verdict") in VERDICTS:
            findings = [
                {"severity": item.get("severity") if item.get("severity") in SEVERITIES else "medium",
                 "text": str(item.get("text", ""))}
                for item in value.get("findings") or [] if isinstance(item, dict)
            ]
            return {"verdict": value["verdict"], "findings": findings}
        start = text.find("{", start + 1)
    return concerns("kritik nevrátil JSON", text)


def _run(args, prompt, seconds):
    return subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=seconds)


def review(data, runner=_run, find=lambda: shutil.which("codex")):
    """Jeden posudek; `runner(args, prompt, timeout)` vrací `CompletedProcess` (ve zkouškách podvržený)."""
    codex = find()
    if not codex:
        return concerns("codex není nainstalovaný")
    prompt = build_prompt(str(data.get("subject") or ""), [str(c) for c in data.get("criteria") or []],
                          data.get("context"))
    with tempfile.TemporaryDirectory(prefix="opora-critic-") as folder:
        last = Path(folder) / "last.txt"
        args = [codex, "exec", "-s", "read-only", "--skip-git-repo-check", "--ephemeral", "--color", "never",
                "-C", folder, "-o", str(last), "-"]
        try:
            done = runner(args, prompt, timeout())
        except subprocess.TimeoutExpired:
            return concerns(f"kritik nestihl odpovědět do {timeout():.0f} s")
        except OSError as error:
            return concerns(f"codex nešel spustit: {error}")
        text = last.read_text(encoding="utf-8", errors="replace") if last.exists() else ""
    text = text.strip() or (done.stdout or "")
    if done.returncode != 0 and not text.strip():
        return concerns(f"codex skončil kódem {done.returncode}", done.stderr)
    return parse(text)


def work(ctx, _runtime):
    """Práce uzlu pro `runtime.detached`: posudek jde vždy portem `main`."""
    given = ctx["input"] if isinstance(ctx["input"], dict) else {}
    data = {**(ctx["node"].get("params") or {}), **given}
    return "main", review(data), {"provider": "openai", "model": "codex"}
