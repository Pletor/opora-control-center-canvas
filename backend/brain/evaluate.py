"""Eval gate Brainu (§3.4, PR 7c): kandidát se aktivuje, jen když na stejné sadě evalu neprohraje s baseline.

Kandidát (`add_candidate`) je nový commit pluginu a verze `candidate`, jejíž baseline je aktivní verze artefaktu.
Sada evalu (`<plugin>/evals/`) je zmrazená: kandidát ji měnit nesmí (422 `evals_frozen`), doplňuje ji jen seed.
`execute` vyexportuje kandidáta i baseline (`Store.export`, rozbalený zip), do obou dá `evals/` z verze kandidáta
(= sada, kterou kandidát nezměnil) a pustí na obou `claude plugin eval` s `--json`. Skóre je
`aggregates.overallScore`, cena `costUsd`; kandidát běží s `--ablation with-without` (report nese i srovnání proti
běhu bez pluginu), baseline s `--ablation none`. Strop ceny obou běhů dohromady `OPORA_BRAIN_EVAL_MAX_USD` (1.0).
Výsledek je řádek `brain_eval_runs` (`running` → `ok` / `error`, aktivace člověkem bez evalu `forced`) navázaný
přes `brain_links(target_kind=eval_run)`. Prošlo = `ok` a skóre ≥ skóre baseline.
"""

import json
import os
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from backend.brain import registry
from backend.brain import operational_eval
from backend.brain.store import Store

DEFAULT_MAX_USD = 1.0
TIMEOUT_SECONDS = 3600
EVALS = "evals"
INPUT_SCHEMA = {"type": "object", "required": ["versionId"], "properties": {"versionId": {"type": "string"}}}
OUTPUT_SCHEMA = {"type": "object", "required": ["score", "baselineScore", "passed"], "properties": {
    "score": {"type": ["number", "null"]}, "baselineScore": {"type": ["number", "null"]}, "passed": {"type": "boolean"}}}


class Refused(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _now():
    return datetime.now(UTC).isoformat()


def max_usd():
    return float(os.environ.get("OPORA_BRAIN_EVAL_MAX_USD") or DEFAULT_MAX_USD)


def add_candidate(db, data_root, artifact, files, message):
    """Zapíše soubory pluginu artefaktu a přidá verzi `candidate` s baseline = aktivní verze; vrací verzi."""
    row = db.execute("SELECT plugin, name FROM brain_artifacts WHERE id=?", (artifact,)).fetchone()
    if row is None:
        raise Refused(404, "artifact_not_found", "Artefakt Brainu neexistuje.")
    if not isinstance(files, dict) or not files or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in files.items()):
        raise Refused(422, "files_invalid", "Tělo potřebuje `files: {relpath: text}` s aspoň jedním souborem.")
    if any(Path(key).parts[:1] == (EVALS,) for key in files):
        raise Refused(422, "evals_frozen", "Sada evals/ je zmrazená; kandidát ji měnit nesmí.")
    active = db.execute("SELECT id, version, content_ref FROM brain_artifact_versions WHERE artifact_id=? AND "
                        "status='active'", (artifact,)).fetchone()
    try:
        sha = Store(data_root).write(row["plugin"], files, message or f"kandidát: {artifact}")
    except ValueError as error:
        raise Refused(422, "files_invalid", str(error)) from error
    if active and sha == active["version"]:
        raise Refused(422, "no_change", "Kandidát nic nemění proti aktivní verzi.")
    content_ref = active["content_ref"] if active else f"skills/{row['name']}/SKILL.md"
    return registry.version(db, registry.add_version(db, artifact, sha, content_ref,
                                                          active and active["id"]))


def _run_row(row):
    value = dict(row)
    value["report"] = json.loads(value.pop("report_json") or "null")
    value["passed"] = passed(value)
    return value


def get_run(db, run_id):
    row = db.execute("SELECT r.*,a.plugin FROM brain_eval_runs r JOIN brain_artifact_versions v ON v.id=r.version_id "
                     "JOIN brain_artifacts a ON a.id=v.artifact_id WHERE r.id=?", (run_id,)).fetchone()
    return _run_row(row) if row else None


def latest(db, version_id):
    row = db.execute("SELECT r.*,a.plugin FROM brain_eval_runs r JOIN brain_artifact_versions v ON v.id=r.version_id "
                     "JOIN brain_artifacts a ON a.id=v.artifact_id WHERE r.version_id=? ORDER BY r.created_at DESC, r.rowid DESC LIMIT 1",
                     (version_id,)).fetchone()
    return _run_row(row) if row else None


def passed(run, plugin=None):
    report = (run or {}).get("report")
    candidate = report.get("candidate") if isinstance(report, dict) else None
    operational = candidate.get("operational") if isinstance(candidate, dict) else None
    if (plugin or (run or {}).get("plugin")) == "opora-control-center" and not operational_eval.passed(operational):
        return False
    return bool(run) and run["status"] == "ok" and run["score"] is not None and run["baseline_score"] is not None \
        and run["score"] >= run["baseline_score"] \
        and (operational is None or isinstance(operational, dict) and operational.get("passed") is True)


def _insert(db, version, status):
    rid = uuid.uuid4().hex
    with db:
        db.execute("INSERT INTO brain_eval_runs(id,version_id,baseline_version_id,status,created_at) VALUES(?,?,?,?,?)",
                   (rid, version["id"], version["baseline_version_id"], status, _now()))
    registry.link(db, version["id"], "eval_run", rid)
    return get_run(db, rid)


def start(db, version_id):
    """Založí běh `running` pro kandidáta s baseline; zámek drží volající."""
    version = registry.version(db, version_id)
    if version is None:
        raise Refused(404, "version_not_found", "Verze artefaktu neexistuje.")
    if version["status"] != "candidate":
        raise Refused(409, "not_candidate", "Eval se pouští jen na kandidáta.")
    if not version["baseline_version_id"]:
        raise Refused(409, "baseline_missing", "Kandidát nemá baseline (artefakt neměl aktivní verzi).")
    return _insert(db, version, "running")


def force(db, version_id):
    """Aktivace člověkem bez prošlého evalu: záznam `forced` (doklad, kdo gate obešel)."""
    return _insert(db, registry.version(db, version_id), "forced")


def claude_path():
    return shutil.which("claude")


def _run(args, cwd, seconds):
    return subprocess.run(args, cwd=cwd, capture_output=True, check=False, text=True, encoding="utf-8",
                          errors="replace", timeout=seconds)


def _checkout(store, plugin, sha, target):
    with zipfile.ZipFile(store.export(plugin, sha)) as archive:
        archive.extractall(target)
    return target


def _summary(report):
    return {"costUsd": report.get("costUsd"), "partial": report.get("partial"),
            "aggregates": report.get("aggregates"),
            **({"operational": report["operational"], "nativeAggregates": report.get("nativeAggregates")} if "operational" in report else {}),
            "cases": [{"name": case.get("name"), "aggregates": case.get("aggregates")}
                      for case in report.get("cases") or []]}


def _eval(claude, plugin_dir, out, budget, ablation, runner, keep_temp=False):
    args = [claude, "plugin", "eval", str(plugin_dir), "--json", str(out), "--ablation", ablation,
            "--max-cost-usd", f"{budget:.2f}", "-j", "2", "--threshold", "0", "--trust-plugin", "--no-publish"]
    if keep_temp:
        args.append("--keep-temp")
    done = runner(args, str(plugin_dir.parent), TIMEOUT_SECONDS)
    if not out.is_file():
        raise RuntimeError(f"claude plugin eval skončil kódem {done.returncode}: {(done.stderr or '')[-500:]}")
    return json.loads(out.read_text(encoding="utf-8"))


def execute(service, run_id, runner=None):
    """Pustí eval kandidáta a baseline a zapíše výsledek běhu; DB jen pod `registry_lock`, eval mimo něj."""
    runner = runner or _run
    with service.registry_lock:
        run = get_run(service.db, run_id)
        candidate = registry.version(service.db, run["version_id"])
        baseline = registry.version(service.db, run["baseline_version_id"])
    store, fields = Store(service.root), {"status": "error"}
    try:
        claude = claude_path()
        if not claude:
            raise RuntimeError("claude není nainstalovaný.")
        with tempfile.TemporaryDirectory(prefix="opora-brain-eval-") as folder:
            folder = Path(folder)
            cand = _checkout(store, candidate["plugin"], candidate["version"], folder / "candidate")
            base = _checkout(store, baseline["plugin"], baseline["version"], folder / "baseline")
            if not (cand / EVALS).is_dir():
                raise RuntimeError("Plugin nemá sadu evals/.")
            shutil.rmtree(base / EVALS, ignore_errors=True)
            shutil.copytree(cand / EVALS, base / EVALS)
            specification = operational_eval.contract(cand, candidate["plugin"])
            budget = max_usd()
            first = _eval(claude, cand, folder / "candidate.json", budget, "with-without", runner, specification is not None)
            spent = float(first.get("costUsd") or 0)
            second = _eval(claude, base, folder / "baseline.json", max(budget - spent, 0.01), "none", runner, specification is not None)
            first = operational_eval.apply(first, specification, cand)
            second = operational_eval.apply(second, specification, base)
        cost = spent + float(second.get("costUsd") or 0)
        partial = bool(first.get("partial") or second.get("partial"))
        fields = {"status": "error" if partial else "ok", "cost_usd": cost,
                  "score": (first.get("aggregates") or {}).get("overallScore"),
                  "baseline_score": (second.get("aggregates") or {}).get("overallScore"),
                  "report_json": json.dumps({"candidate": _summary(first), "baseline": _summary(second),
                                             **({"error": "strop ceny, výsledek je neúplný"} if partial else {})},
                                            ensure_ascii=False)}
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired, zipfile.BadZipFile) as error:
        fields["report_json"] = json.dumps({"error": f"{type(error).__name__}: {error}"[:1000]}, ensure_ascii=False)
    with service.registry_lock:
        db = service.db
        with db:
            db.execute(f"UPDATE brain_eval_runs SET {', '.join(f'{key}=?' for key in fields)} WHERE id=?",
                       (*fields.values(), run_id))
            if fields.get("score") is not None:
                db.execute("UPDATE brain_artifact_versions SET eval_score=? WHERE id=?",
                           (fields["score"], candidate["id"]))
        return get_run(db, run_id)


def evaluate(service, version_id, runner=None):
    """Založí a hned vykoná eval (uzel `brain_eval`); vrací uložený běh."""
    with service.registry_lock:
        run = start(service.db, version_id)
    return execute(service, run["id"], runner)


def work(ctx, runtime):
    """Práce uzlu `brain_eval` pro `runtime.detached`: vstup `{versionId}` (nebo `params`), výstup portem `main`."""
    given = ctx["input"] if isinstance(ctx["input"], dict) else {}
    version_id = {**(ctx["node"].get("params") or {}), **given}.get("versionId")
    if not version_id:
        raise ValueError("Uzel brain_eval potřebuje versionId.")
    run = evaluate(runtime.service, version_id)
    output = {"score": run["score"], "baselineScore": run["baseline_score"], "passed": run["passed"]}
    return "main", output, {"cost_usd": run["cost_usd"]}
