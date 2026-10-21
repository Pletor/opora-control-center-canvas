"""Run TLC over every positive and negative config declared in tools/formal/*/cases.json.

Same script in CI (.github/workflows/formal.yml, check run `formal/tlc`) and locally:

    python tools/formal/run.py --jar C:/cache/tla2tools-1.7.4.jar --summary formal-summary.json
    python tools/formal/run.py --download --cache-dir ~/.cache/opora-tla

A positive config must exhaust its finite state space without error. A negative
(mutant) config must fail with exactly the declared invariant; a negative that passes
means the spec became vacuous for that property and fails the run. The summary JSON is
machine-readable; under GitHub Actions each failure also becomes an `::error` annotation
whose message is the case JSON, which OporaHub reads back as an attention item.
Exit code: 0 all expectations met, 1 an expectation failed, 2 runner/tool unavailable.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECK_NAME = "formal/tlc"
SCHEMA_VERSION = 1
PINNED = {"release": "v1.7.4", "tlc": "TLC2 2.19 (08 August 2024), revision 5a47802",
          "url": "https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar",
          "sha256": "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"}
BLOCKED_ENV = {"JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH", "JAVA_OPTS"}
STATS = re.compile(r"([\d,]+) states generated, ([\d,]+) distinct states found, ([\d,]+) states left on queue")
STATE = re.compile(r"^State (\d+): <([A-Za-z_][\w]*)", re.MULTILINE)


class RunnerError(RuntimeError):
    """The tool chain is unavailable; nothing was checked."""


def number(text):
    return int(text.replace(",", ""))


def parse_output(text, exit_code):
    """Classify one TLC log: pass | violation | incomplete | error, plus bounded statistics."""
    text = text.replace("\r\n", "\n")
    parsed = {"result": "error", "violated": None, "violationKind": None, "exitCode": exit_code,
              "generated": None, "distinct": None, "queue": None, "depth": None, "trace": []}
    stats = STATS.findall(text)
    if stats:
        parsed["generated"], parsed["distinct"], parsed["queue"] = (number(v) for v in stats[-1])
    depth = re.search(r"The depth of the complete state graph search is (\d+)", text)
    parsed["depth"] = int(depth.group(1)) if depth else None
    parsed["trace"] = [name for _, name in STATE.findall(text)][:64]
    invariant = re.search(r"^Error: Invariant (\w+) is violated\.", text, re.MULTILINE)
    if re.search(r"\bsimulation\b", text, re.IGNORECASE) and "Running breadth-first" not in text:
        parsed["result"] = "incomplete"
    elif invariant:
        parsed.update(result="violation", violated=invariant.group(1), violationKind="invariant")
    elif re.search(r"^Error: Temporal properties were violated\.", text, re.MULTILINE):
        parsed.update(result="violation", violated="temporal-property", violationKind="property")
    elif re.search(r"^Error: Deadlock reached\.", text, re.MULTILINE):
        parsed.update(result="violation", violated="deadlock", violationKind="deadlock")
    elif (exit_code == 0 and "Model checking completed. No error has been found." in text
          and parsed["queue"] == 0 and "Error:" not in text):
        parsed["result"] = "pass"
    elif exit_code == 0:
        parsed["result"] = "incomplete"
    return parsed


def evaluate(case, parsed):
    """Compare one parsed run with its declared expectation; `kind` names the failure."""
    if case["expect"] == "pass":
        if parsed["result"] == "pass":
            return True, None
        return False, "positive_violation" if parsed["result"] == "violation" else "runner_error"
    if parsed["result"] == "violation" and parsed["violated"] == case["invariant"]:
        return True, None
    if parsed["result"] == "pass":
        return False, "negative_not_detected"
    return False, "wrong_violation" if parsed["result"] == "violation" else "runner_error"


def load_suites(root=ROOT, only=None):
    suites = []
    for manifest in sorted(root.glob("*/cases.json")):
        if only and manifest.parent.name != only:
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for case in data["cases"]:
            if case["expect"] not in ("pass", "violation") or (case["expect"] == "violation") != ("invariant" in case):
                raise ValueError(f"Invalid case {case.get('name')} in {manifest}.")
        suites.append({"model": manifest.parent.name, "dir": manifest.parent, "spec": data["spec"],
                       "cases": data["cases"]})
    return suites


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned_jar(jar=None, download=False, cache_dir=None):
    """Return a jar path whose SHA256 equals the pin; download only when asked."""
    candidates = [Path(jar)] if jar else []
    cache = Path(cache_dir or Path.home() / ".cache" / "opora-tla").expanduser()
    candidates.append(cache / f"tla2tools-{PINNED['release']}.jar")
    for candidate in candidates:
        if candidate.is_file() and sha256(candidate) == PINNED["sha256"]:
            return candidate
    if jar and Path(jar).is_file():
        raise RunnerError("tla2tools.jar SHA256 does not match the pinned v1.7.4 distribution.")
    if not download:
        raise RunnerError("Pinned tla2tools.jar not found; pass --jar or --download.")
    cache.mkdir(parents=True, exist_ok=True)
    partial = cache / "tla2tools.partial"
    with urllib.request.urlopen(PINNED["url"], timeout=60) as response:  # Fixed https pin, hash-checked below.
        partial.write_bytes(response.read(64 * 1024 * 1024))
    if sha256(partial) != PINNED["sha256"]:
        partial.unlink()
        raise RunnerError("Downloaded tla2tools.jar failed the pinned SHA256 check.")
    target = candidates[-1]
    partial.replace(target)
    return target


def run_case(java, jar, suite, case, workdir, timeout, workers):
    folder = Path(workdir) / suite["model"] / case["name"]
    folder.mkdir(parents=True)
    for name in (suite["spec"], case["config"]):
        shutil.copyfile(suite["dir"] / name, folder / name)
    command = [java, "-XX:+UseParallelGC", "-Xmx2g", "-cp", str(jar), "tlc2.TLC", "-workers", str(workers),
               "-fp", "0", "-seed", "1", "-config", case["config"], "-metadir", str(folder / "states"),
               "-cleanup", suite["spec"]]
    env = {key: value for key, value in os.environ.items() if key.upper() not in BLOCKED_ENV}
    started = time.monotonic()
    try:
        done = subprocess.run(command, cwd=folder, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=timeout, check=False)
        code, text = done.returncode, (done.stdout + done.stderr).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as expired:
        code = -1
        text = (expired.stdout or b"").decode("utf-8", errors="replace") + "\n[runner] wall timeout\n"
    text = text.replace("\r\n", "\n")
    (folder / "tlc.log").write_text(text, encoding="utf-8", newline="\n")
    return code, text, round(time.monotonic() - started, 1), folder / "tlc.log"


def case_result(suite, case, parsed, seconds):
    ok, kind = evaluate(case, parsed)
    return {"model": suite["model"], "case": case["name"], "config": case["config"],
            "expect": case["expect"], "expectedInvariant": case.get("invariant"), "ok": ok, "kind": kind,
            "observed": parsed, "seconds": seconds}


def annotation(result):
    """GitHub workflow command; the message is the case JSON so Canvas can classify it."""
    payload = {key: result[key] for key in ("model", "case", "config", "expect", "expectedInvariant", "kind")}
    payload["violated"] = result["observed"]["violated"]
    message = json.dumps(payload, separators=(",", ":")).replace("%", "%25").replace("\n", "%0A")
    return f"::error title={CHECK_NAME} {result['kind']}::{message}"


def summary(results, commit=None):
    return {"schemaVersion": SCHEMA_VERSION, "check": CHECK_NAME, "commitSha": commit,
            "tool": {"name": "tlc", **{k: PINNED[k] for k in ("release", "tlc", "sha256")}},
            "ok": bool(results) and all(item["ok"] for item in results), "cases": results,
            "evidenceKinds": {"tlc": "connected", "lean": "connected"}}


def markdown(document):
    lines = [f"### {CHECK_NAME}: {'ok' if document['ok'] else 'FAILED'}", "",
             "| model | case | expect | observed | distinct states | result |", "|---|---|---|---|---|---|"]
    for item in document["cases"]:
        expect = item["expect"] + (f" {item['expectedInvariant']}" if item["expectedInvariant"] else "")
        violated = item["observed"]["violated"]
        observed = item["observed"]["result"] + (f" {violated}" if violated else "")
        lines.append(f"| {item['model']} | {item['case']} | {expect} | {observed} | "
                     f"{item['observed']['distinct']} | {'ok' if item['ok'] else item['kind']} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jar", default=os.environ.get("OPORA_TLC_JAR"))
    parser.add_argument("--download", action="store_true", help="fetch the pinned jar into --cache-dir")
    parser.add_argument("--cache-dir")
    parser.add_argument("--summary", help="write the machine-readable summary JSON here")
    parser.add_argument("--model", help="only this tools/formal/<model> suite")
    parser.add_argument("--case", action="append", help="only these case names (repeatable)")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per case")
    parser.add_argument("--workers", default="1")
    parser.add_argument("--keep", help="keep TLC work folders here instead of a temp dir")
    args = parser.parse_args(argv)
    try:
        suites = load_suites(only=args.model)
        jar = pinned_jar(args.jar, args.download, args.cache_dir)
        java = shutil.which("java")
        if not java:
            raise RunnerError("Java is not on PATH.")
    except (RunnerError, OSError, ValueError) as error:
        print(f"formal/tlc runner unavailable: {error}", file=sys.stderr)
        return 2
    workdir = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="opora-tlc-"))
    workdir.mkdir(parents=True, exist_ok=True)
    results, annotate = [], os.environ.get("GITHUB_ACTIONS") == "true"
    for suite in suites:
        for case in suite["cases"]:
            if args.case and case["name"] not in args.case:
                continue
            code, text, seconds, log = run_case(java, jar, suite, case, workdir, args.timeout, args.workers)
            result = case_result(suite, case, parse_output(text, code), seconds)
            results.append(result)
            verdict = "ok" if result["ok"] else f"FAILED ({result['kind']})"
            print(f"{suite['model']}/{case['name']}: {verdict} exit={code} {seconds}s log={log}")
            if annotate and not result["ok"]:
                print(annotation(result))
    document = summary(results, os.environ.get("GITHUB_SHA"))
    if args.summary:
        Path(args.summary).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(markdown(document))
    return 0 if document["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
