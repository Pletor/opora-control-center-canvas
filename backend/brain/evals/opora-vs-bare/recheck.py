"""Kontrola bez modelu: šablona + patch → pracovní kopie → `grade.check_workspace`.

    python -B recheck.py patch --case C02                                   # nezměněná šablona (čeká se checks_pass 0)
    python -B recheck.py patch --case C02 --patch oracles/C02/oracle.patch  # oracle (čeká se checks_pass 1)
    python -B recheck.py variant --variant baseline [--cases C01]          # přepočet metrik už proběhlých běhů

`variant` obnoví výstup každého řádku A/B z šablony a jeho diffu (`git apply --ignore-whitespace`), znovu ho
zkontroluje (Q1–Q4, Q8, screenshoty do `<varianta>/shots/`) a z `raw/` a diffu dopočítá C4, C5, P4, P5
(P1–P3 jen když existuje snímek `<varianta>/opora/<id>_rep<k>.json`). Řádky přepíše na místě; původní soubor
uloží jako `results.before-recheck.jsonl`. Žádný model, žádná OPORA. Pracovní kopie v `--work-root` (C:\\oe).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import sys
from pathlib import Path

FLOW = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(FLOW))
import grade  # noqa: E402
import metrics  # noqa: E402


def sh(cmd, cwd):
    r = subprocess.run([shutil.which(cmd[0]) or cmd[0], *cmd[1:]], cwd=cwd, capture_output=True, check=False)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd[:4])} -> {r.returncode}: {(r.stdout + r.stderr).decode('utf-8', 'replace')[-600:]}")
    return r.stdout.decode("utf-8", "replace")


def build_workspace(case_id: str, patch: Path | None, dest: Path) -> Path:
    """Kopie šablony případu, git commit, volitelně `git apply` patche (diff běhu nebo oracle)."""
    tmpl = FLOW / "templates" / grade.SPECS[case_id]["template"]
    for _ in range(5):  # zamčené soubory po spadlém běhu (vite preview, esbuild) se uvolní až po ukončení
        if not dest.exists():
            break
        grade.kill_leftovers(dest)
        grade.rmtree_force(dest)
        time.sleep(1)
    if dest.exists():
        raise RuntimeError(f"pracovní kopii {dest} nejde smazat")
    shutil.copytree(tmpl, dest, ignore=shutil.ignore_patterns("node_modules", "dist"))
    git = ["git", "-c", "user.name=eval", "-c", "user.email=eval@local", "-c", "core.autocrlf=false"]
    sh([*git, "init", "-q", "-b", "main"], dest)
    sh([*git, "add", "-A"], dest)
    sh([*git, "commit", "-qm", "šablona"], dest)
    if patch is not None and Path(patch).read_text(encoding="utf-8").strip():
        sh([*git, "apply", "--ignore-whitespace", "--whitespace=nowarn", str(Path(patch).resolve())], dest)
    return dest


def cmd_patch(args):
    patch = Path(args.patch) if args.patch else None
    name = args.name or (patch.parent.name + "-" + patch.stem if patch else "t0")
    ws = build_workspace(args.case, patch, Path(args.work_root) / f"recheck-{args.case}-{name}")
    shots = Path(args.shots_dir) if args.shots_dir else None
    res = grade.check_workspace(args.case, ws, shots_dir=shots, shot_prefix=f"{args.case}_{name}")
    failed = [k for k, v in res["checks"].items() if not v]
    print(json.dumps({"case": args.case, "patch": str(patch) if patch else None, "grade": res["grade"],
                      "failed": {k: res["notes"].get(k, "") for k in failed},
                      "a11y_failed": {k: res["notes"].get(f"a11y:{k}", "") for k, v in res["a11y"].items() if v is False},
                      "tests": res["tests"]}, ensure_ascii=False, indent=2))
    if not args.keep:
        grade.kill_leftovers(ws)
        grade.rmtree_force(ws)
    return 0


def cmd_variant(args):
    vdir = FLOW / args.variant
    path = vdir / "results.jsonl"
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    shutil.copy2(path, vdir / "results.before-recheck.jsonl")
    for row in rows:
        meta = row.get("meta", {})
        if row.get("status") != "ok" or meta.get("arm") not in ("A", "B") or (wanted and meta["case"] not in wanted):
            continue
        pid, rep = row["prompt_id"], row["rep"]
        ws = build_workspace(meta["case"], FLOW / meta["diff"], Path(args.work_root) / f"recheck-{pid}-r{rep}")
        checked = grade.check_workspace(meta["case"], ws, shots_dir=vdir / "shots", shot_prefix=f"{pid}_rep{rep}")
        trace_path = vdir / "traces" / f"{pid}_rep{rep}.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else []
        tm = metrics.trace_metrics(vdir / "raw" / f"{pid}_rep{rep}.jsonl", metrics.opora_base_from_trace(trace))
        dm = metrics.diff_metrics((FLOW / meta["diff"]).read_text(encoding="utf-8"))
        snap_path = vdir / "opora" / f"{pid}_rep{rep}.json"
        om = metrics.opora_metrics(json.loads(snap_path.read_text(encoding="utf-8")), ws) if snap_path.exists() else None
        metrics.apply_to_row(row, checked, tm, dm, om)
        meta["rechecked"] = True
        print(f"  {pid} rep{rep}: {json.dumps(row['grade'], ensure_ascii=False)}  cost {json.dumps(row['cost'], ensure_ascii=False)[:200]}",
              file=sys.stderr)
        grade.kill_leftovers(ws)
        grade.rmtree_force(ws)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Kontrola bez modelu (oracle, T0, přepočet běhů)")
    p.add_argument("--work-root", default=os.environ.get("OPORA_EVAL_WORK_ROOT", r"C:\oe"))
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("patch")
    a.add_argument("--case", required=True)
    a.add_argument("--patch")
    a.add_argument("--name")
    a.add_argument("--shots-dir")
    a.add_argument("--keep", action="store_true")
    v = sub.add_parser("variant")
    v.add_argument("--variant", required=True)
    v.add_argument("--cases", default="")
    args = p.parse_args(argv)
    return cmd_patch(args) if args.cmd == "patch" else cmd_variant(args)


if __name__ == "__main__":
    sys.exit(main())
