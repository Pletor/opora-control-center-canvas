"""Build the OporaHub Lean proofs and audit every theorem's axioms (check run `formal/lean`).

    python tools/formal/lean/audit.py --summary lean-summary.json            # build + audit + vectors
    python tools/formal/lean/audit.py --trusted --summary lean-summary.json  # no PR executable runs

Steps, each a failure `kind` when it fails:
1. `forbidden_construct`: a source scan (before any Lean code runs) rejects `sorry`, `admit`,
   new `axiom`s, `native_decide`, `implemented_by`/`extern`, `unsafe`, `opaque`, `#eval`,
   `run_cmd`, `initialize`, user `macro`/`syntax`/`elab`, kernel-check options and imports
   outside `OporaHub.*`. Proof files stay a metaprogram-free subset, so elaborating them
   cannot execute PR-controlled code.
2. `build_failed`: `lake build` (the kernel checks every proof).
3. `nonstandard_axiom` / `audit_incomplete`: `#print axioms` on every declared theorem; only
   propext, Classical.choice and Quot.sound are allowed (sorryAx never), and every theorem
   found in the sources must appear in the audit.
4. `vectors_drift` (not with --trusted): `lake exe vectors` must equal the committed
   vectors.json that backend/canvas/test_opora_lean_differential.py runs the Python against.
Exit 0 = clean, 1 = a check failed, 2 = Lean toolchain unavailable.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECK_NAME = "formal/lean"
SCHEMA_VERSION = 1
ALLOWED_AXIOMS = ("Classical.choice", "Quot.sound", "propext")
FORBIDDEN = [(re.compile(pattern, re.MULTILINE), token) for pattern, token in (
    (r"\bsorry\b", "sorry"), (r"\badmit\b", "admit"), (r"^\s*(?:private\s+|protected\s+)?axiom\b", "axiom"),
    (r"\bnative_decide\b", "native_decide"), (r"\bimplemented_by\b", "implemented_by"), (r"@\[\s*extern", "extern"),
    (r"\bunsafe\b", "unsafe"), (r"\bopaque\b", "opaque"), (r"#eval\b", "#eval"), (r"\brun_cmd\b", "run_cmd"),
    (r"\brun_tac\b", "run_tac"), (r"\b(?:builtin_)?initialize\b", "initialize"),
    (r"^\s*(?:macro|macro_rules|syntax|elab|elab_rules|declare_syntax_cat)\b", "metaprogram"),
    (r"set_option\s+debug\.", "debug-option"), (r"\bdecreasing_by\s+sorry\b", "sorry"))]
IMPORT = re.compile(r"^\s*import\s+(.+)$", re.MULTILINE)
DECL = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+)?theorem\s+([^\s:({\[]+)", re.MULTILINE)
SCOPE = re.compile(r"^\s*(namespace|end)\b\s*([\w.]*)", re.MULTILINE)
AXIOMS = re.compile(r"'([^']+)' depends on axioms: \[([^\]]*)\]")
NO_AXIOMS = re.compile(r"'([^']+)' does not depend on any axioms")


class ToolMissing(RuntimeError):
    pass


def strip_comments(text):
    text = re.sub(r"/-.*?-/", lambda match: re.sub(r"[^\n]", " ", match.group(0)), text, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", text)


def sources(root=ROOT):
    return sorted([root / "OporaHub.lean", *(root / "OporaHub").rglob("*.lean")])


def scan(files, root=ROOT):
    """Forbidden constructs and imports; runs on text only, before Lean executes anything."""
    found = []
    for path in files:
        text = strip_comments(path.read_text(encoding="utf-8"))
        rel = path.relative_to(root).as_posix()
        for pattern, token in FORBIDDEN:
            for match in pattern.finditer(text):
                found.append({"file": rel, "line": text.count("\n", 0, match.start()) + 1, "token": token})
        for match in IMPORT.finditer(text):
            for module in match.group(1).split():
                if not module.startswith("OporaHub"):
                    found.append({"file": rel, "line": text.count("\n", 0, match.start()) + 1,
                                  "token": f"import {module}"})
    return found


def theorems(files, root=ROOT):
    """Fully qualified theorem names with their module, from `namespace`/`end` scoping."""
    result = []
    for path in files:
        text = strip_comments(path.read_text(encoding="utf-8"))
        module = path.relative_to(root).with_suffix("").as_posix().replace("/", ".")
        events = sorted([(m.start(), "scope", m) for m in SCOPE.finditer(text)]
                        + [(m.start(), "decl", m) for m in DECL.finditer(text)], key=lambda item: item[0])
        stack = []
        for _, kind, match in events:
            if kind == "scope":
                if match.group(1) == "namespace":
                    stack.append(match.group(2))
                elif stack:
                    stack.pop()
            else:
                result.append({"name": ".".join([*stack, match.group(1)]), "module": module})
    return result


def lake():
    found = shutil.which("lake") or str(Path.home() / ".elan" / "bin" / ("lake.exe" if os.name == "nt" else "lake"))
    if not Path(found).is_file():
        raise ToolMissing("lake (elan) is not on PATH.")
    return found


def run(command, cwd=ROOT, timeout=1800):
    done = subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False)
    return done.returncode, (done.stdout + done.stderr).decode("utf-8", errors="replace").replace("\r\n", "\n")


def parse_axioms(text):
    result = {name: [] for name in NO_AXIOMS.findall(text)}
    for name, axioms in AXIOMS.findall(text):
        result[name] = sorted(item.strip() for item in axioms.split(",") if item.strip())
    return result


def audit(declared, printed):
    """Per-theorem records plus failures; a theorem missing from the output is a failure."""
    records, failures = [], []
    for item in declared:
        axioms = printed.get(item["name"])
        bad = None if axioms is None else sorted(set(axioms) - set(ALLOWED_AXIOMS))
        records.append({**item, "axioms": axioms, "ok": axioms is not None and not bad})
        if axioms is None:
            failures.append({"kind": "audit_incomplete", "theorem": item["name"]})
        elif bad:
            failures.append({"kind": "nonstandard_axiom", "theorem": item["name"], "axioms": bad})
    return records, failures


def toolchain(root=ROOT):
    return (root / "lean-toolchain").read_text(encoding="utf-8").strip()


def check(root=ROOT, trusted=False, commit=None):
    files = sources(root)
    declared = theorems(files, root)
    document = {"schemaVersion": SCHEMA_VERSION, "check": CHECK_NAME, "commitSha": commit,
                "tool": {"name": "lean", "toolchain": toolchain(root)}, "trusted": trusted,
                "allowedAxioms": list(ALLOWED_AXIOMS), "forbidden": scan(files, root), "theorems": [],
                "failures": [], "vectors": "skipped" if trusted else None, "ok": False}
    if document["forbidden"]:
        document["failures"].append({"kind": "forbidden_construct", "found": document["forbidden"][:32]})
        document["theorems"] = [{**item, "axioms": None, "ok": False} for item in declared]
        return document
    binary = lake()
    code, text = run([binary, "build", "OporaHub"] if trusted else [binary, "build"], root)
    if code != 0:
        document["failures"].append({"kind": "build_failed", "log": text[-3000:]})
        return document
    with tempfile.TemporaryDirectory(prefix="opora-lean-audit-") as folder:
        script = Path(folder) / "Audit.lean"
        script.write_text("import OporaHub\n" + "".join(f"#print axioms {item['name']}\n" for item in declared),
                          encoding="utf-8")
        code, text = run([binary, "env", "lean", str(script)], root)
    document["theorems"], failures = audit(declared, parse_axioms(text))
    document["failures"] += failures
    if code != 0 and not failures:
        document["failures"].append({"kind": "audit_incomplete", "log": text[-3000:]})
    if not trusted:
        code, text = run([binary, "exe", "vectors"], root)
        committed = json.loads((root / "vectors.json").read_text(encoding="utf-8"))
        try:
            fresh = json.loads(text) if code == 0 else None
        except ValueError:
            fresh = None
        document["vectors"] = "match" if fresh == committed else "drift"
        if fresh != committed:
            document["failures"].append({"kind": "vectors_drift"})
    document["ok"] = bool(declared) and not document["failures"]
    return document


def annotations(document):
    """GitHub workflow commands: one notice with the axiom audit, one error per failure."""
    audit_note = {"toolchain": document["tool"]["toolchain"], "trusted": document["trusted"], "ok": document["ok"],
                  "theorems": [[item["name"], item["axioms"]] for item in document["theorems"]]}
    lines = [f"::notice title={CHECK_NAME} audit::{json.dumps(audit_note, separators=(',', ':'))}"]
    for failure in document["failures"]:
        payload = {key: value for key, value in failure.items() if key != "log"}
        message = json.dumps(payload, separators=(",", ":")).replace("%", "%25").replace("\n", "%0A")
        lines.append(f"::error title={CHECK_NAME} {failure['kind']}::{message}")
    return lines


def markdown(document):
    lines = [f"### {CHECK_NAME}: {'ok' if document['ok'] else 'FAILED'} ({document['tool']['toolchain']})", "",
             "| theorem | axioms | ok |", "|---|---|---|"]
    lines += [f"| `{item['name']}` | {', '.join(item['axioms'] or []) or '—'} | {'ok' if item['ok'] else 'NO'} |"
              for item in document["theorems"]]
    lines += [f"- **{failure['kind']}** {json.dumps({k: v for k, v in failure.items() if k not in ('kind', 'log')})}"
              for failure in document["failures"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--summary")
    parser.add_argument("--trusted", action="store_true", help="build only the proof library; run no PR executable")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    try:
        document = check(Path(args.root), args.trusted, os.environ.get("OPORA_PR_HEAD_SHA") or os.environ.get("GITHUB_SHA"))
    except ToolMissing as error:
        print(f"formal/lean runner unavailable: {error}", file=sys.stderr)
        return 2
    if args.summary:
        Path(args.summary).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    for item in document["theorems"]:
        print(f"{item['name']}: {'ok' if item['ok'] else 'FAILED'} axioms={item['axioms']}")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("\n".join(annotations(document)))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(markdown(document))
    print(f"{CHECK_NAME}: {'ok' if document['ok'] else 'FAILED'} {[f['kind'] for f in document['failures']]}")
    return 0 if document["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
