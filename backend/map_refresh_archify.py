"""Bounded private Archify generation from one sanitized source snapshot."""

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .llm_runs import _WindowsJob

TOTAL_SECONDS = 600
MAX_TURNS = 10
MAX_AGENT_BYTES = 512 * 1024
MAX_SPEC_BYTES = 512 * 1024
REVISION = re.compile(r"^[a-f0-9]{40}$")
SAFE_EVIDENCE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/ -]{0,239}$")
FILES = {
    "candidate": "map.architecture.json",
    "html": "map.architecture.html",
    "spec": "SPEC.md",
    "deliver": "deliver-receipt.json",
    "validate": "validate-receipt.json",
    "visual": "visual-check-receipt.json",
    "evidence": "evidence.json",
}


class ArchifyBuildError(ValueError):
    """A safe, publishable-to-users failure from the private build boundary."""


def _cancelled(cancel):
    if cancel is None:
        return False
    if callable(cancel):
        return bool(cancel())
    probe = getattr(cancel, "is_set", None)
    return bool(probe()) if callable(probe) else bool(cancel)


def _safe_node_env():
    """Keep Node deterministic without inheriting provider credentials."""
    names = (
        "PATH",
        "SystemRoot",
        "SYSTEMROOT",
        "ComSpec",
        "COMSPEC",
        "TEMP",
        "TMP",
        "LOCALAPPDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
    )
    env = {name: os.environ[name] for name in names if os.environ.get(name)}
    env["NO_COLOR"] = "1"
    return env


def _terminate(process, job):
    try:
        if job is not None:
            return job.terminate_wait(timeout=5)
        process.kill()
        process.wait(timeout=5)
        return process.poll() is not None
    except (OSError, subprocess.SubprocessError):
        return False


def _run_process(command, *, cwd, env, deadline, cancel, stdin=None):
    """Run one contained child, returning bounded UTF-8 stdout or raising safely."""
    if _cancelled(cancel):
        raise ArchifyBuildError("Běh Archify byl zrušen.")
    job = None
    process = None
    try:
        options = {
            "cwd": str(cwd),
            "env": env,
            "stdin": subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
        }
        if os.name == "nt":
            job = _WindowsJob()
            flags = _WindowsJob.CREATE_SUSPENDED | _WindowsJob.CREATE_NO_WINDOW
            process = subprocess.Popen(command, creationflags=flags, **options)
            job.assign_and_resume(process)
        else:
            process = subprocess.Popen(command, start_new_session=True, **options)
        while True:
            if _cancelled(cancel):
                _terminate(process, job)
                raise ArchifyBuildError("Běh Archify byl zrušen.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate(process, job)
                raise ArchifyBuildError("Archify překročil společný limit 600 sekund.")
            try:
                stdout, stderr = process.communicate(
                    input=stdin.encode("utf-8") if isinstance(stdin, str) else stdin,
                    timeout=min(0.25, remaining),
                )
                break
            except subprocess.TimeoutExpired:
                # communicate() may be called again after TimeoutExpired; it retains
                # already collected pipe data and keeps the child contained.
                stdin = None
        if len(stdout) + len(stderr) > MAX_AGENT_BYTES:
            raise ArchifyBuildError("Výstup Archify procesu překročil bezpečný limit.")
        if process.returncode != 0:
            try:
                envelope = json.loads(stdout)
            except (ValueError, UnicodeError):
                envelope = {}
            if not isinstance(envelope, dict):
                envelope = {}
            # Dosažení průzkumného limitu není hotový artefakt; dovolí pouze dokončovací fázi.
            if Path(command[0]).name.lower().startswith('claude') and envelope.get('subtype') == 'error_max_turns':
                return stdout.decode('utf-8')
            stage = 'Claude' if Path(command[0]).name.lower().startswith('claude') else 'Archify ' + str(command[2])
            reason = envelope.get('subtype', 'nonzero_exit')
            raise ArchifyBuildError(f'{stage} nedokončil běh (exit {process.returncode}, {reason}).')
        return stdout.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ArchifyBuildError("Proces Archify vrátil neplatný textový výstup.") from exc
    except OSError as exc:
        raise ArchifyBuildError("Proces Archify nelze bezpečně spustit.") from exc
    finally:
        if process is not None and process.poll() is None:
            _terminate(process, job)
        if job is not None:
            job.close()


def _package_file(name):
    path = Path(__file__).resolve().parents[1] / "vendor" / "archify" / "archify" / name
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ArchifyBuildError("Původní balíček Archify není dostupný.") from exc


def _prompt(source_revision):
    skill = _package_file("SKILL.md")
    schema = _package_file("schemas/architecture.schema.json")
    example = _package_file("examples/web-app.architecture.json")
    return f"""You are the single bounded author for an original Archify architecture map.
Analyze ONLY the sanitized snapshot in your current directory. Use only Read, Glob, and Grep.
You have at most SIX exploration rounds. Batch reads, avoid exhaustive browsing and repeated line-number searches.
Read graphify-out/GRAPH_REPORT.md first when present, then only the key source files needed for a small evidence-backed architecture.
Reserve your final response for the required JSON, not a plan. If exploration is cut short, a tools-disabled finalization follows in the same session.
Do not use Bash, Write, Edit, network access, MCP, project instructions, credentials, or any source outside this snapshot.

Return exactly one JSON object and no Markdown fences. Its keys must be exactly candidate, specification, evidence.
- candidate: a COMPLETE RENDERABLE Archify architecture JSON, not merely topology. Set schema_version=1, diagram_type=architecture, meta.quality_profile=showcase. Prefer 6-8 primary components, at most 12. Every component MUST include numeric pos [x,y] and size [w,h], like the example. Include a fitting meta.viewBox. Automatic edge routing does NOT place nodes automatically. Keep labels and routes clear and use sparse connections.
- Every component must also have sources for LOCAL validation by the caller. There is NO verified public repository URL: do not invent meta.repository. The caller stores sources in a local evidence sidecar, not in the renderer's public-repository link fields.
- specification: concise Czech Markdown explaining the architecture and evidence. Do not include a revision line; the caller supplies it.
- evidence: nonempty objects with exactly path, line, identifier. path is source-relative, line is 1-based, and that exact identifier must occur on that exact line. Every candidate component source path+line must occur in evidence.
Do not invent components, protocols, APIs, paths, or source claims. Prefer the optional graphify-out report only when it is itself grounded in this snapshot.
The caller will validate with original native Archify CLI and reject all warnings/errors, so use automatic routes first and no unsupported fields.

Required source revision: {source_revision}

--- Original Archify SKILL ---
{skill}
--- Original architecture schema ---
{schema}
--- Original architecture example (shape only, never copy facts) ---
{example}
"""


def _claude_command():
    claude = shutil.which("claude")
    if not claude:
        raise ArchifyBuildError("Claude Code Sonnet není lokálně dostupný.")
    settings = {
        "disableAllHooks": True,
        "permissions": {"deny": ["Bash", "Write", "Edit", "Read(**/.env)", "Read(**/.env.*)"]},
    }
    return [
        claude,
        "-p",
        "--model",
        "sonnet",
        "--max-turns",
        str(MAX_TURNS),
        "--output-format",
        "json",
        "--tools",
        "Read,Glob,Grep",
        "--allowedTools",
        "Read,Glob,Grep",
        "--permission-mode",
        "dontAsk",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--setting-sources",
        "user",
        "--settings",
        json.dumps(settings, separators=(",", ":")),
    ]


def _json_object(raw, label):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ArchifyBuildError(f"{label} neposkytl platný JSON.") from exc
    if not isinstance(value, dict):
        raise ArchifyBuildError(f"{label} neposkytl JSON objekt.")
    return value


def _agent_payload(raw):
    envelope = _json_object(raw, "Claude")
    content = envelope.get("result", raw)
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_AGENT_BYTES:
        raise ArchifyBuildError("Claude neposkytl bezpečný návrh Archify.")
    if content.strip().startswith('```json\n') and content.strip().endswith('\n```'):
        content = content.strip()[8:-4]
    payload = _json_object(content, "Claude")
    if set(payload) != {"candidate", "specification", "evidence"}:
        raise ArchifyBuildError("Claude neposkytl očekávanou strukturu návrhu Archify.")
    if not isinstance(payload["candidate"], dict) or not isinstance(payload["specification"], str):
        raise ArchifyBuildError("Claude neposkytl kandidáta a specifikaci Archify.")
    if len(payload["specification"].encode("utf-8")) > MAX_SPEC_BYTES or not isinstance(
        payload["evidence"], list
    ):
        raise ArchifyBuildError("Claude poskytl příliš velký nebo neplatný důkaz Archify.")
    return payload


def _source_root(root):
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ArchifyBuildError("Sanitizovaný zdroj Archify není dostupný adresář.") from exc
    if (
        not resolved.is_dir()
        or (resolved / ".git").exists()
        or (resolved / "vendor").exists()
        or (resolved / "CLAUDE.md").exists()
        or (resolved / ".claude").exists()
    ):
        raise ArchifyBuildError("Zdroj Archify není očekávaný sanitizovaný snapshot.")
    if any(resolved.glob(".env*")):
        raise ArchifyBuildError("Zdroj Archify nesmí obsahovat soubory .env.")
    return resolved


def _evidence_path(source_root, path):
    if not isinstance(path, str) or not SAFE_EVIDENCE_PATH.fullmatch(path) or "\\" in path:
        raise ArchifyBuildError("Claude poskytl nebezpečnou cestu důkazu.")
    candidate = (source_root / path).resolve()
    if source_root not in candidate.parents or not candidate.is_file():
        raise ArchifyBuildError("Claude poskytl důkaz mimo sanitizovaný snapshot.")
    return candidate


def _validate_evidence(source_root, candidate, evidence):
    components = candidate.get("components")
    if not isinstance(components, list) or not components:
        raise ArchifyBuildError("Kandidát Archify nemá komponenty.")
    if candidate.get("schema_version") != 1 or candidate.get("diagram_type") != "architecture":
        raise ArchifyBuildError("Kandidát nemá původní Archify architecture kontrakt.")
    if candidate.get("meta", {}).get("quality_profile") != "showcase":
        raise ArchifyBuildError("Kandidát musí používat Archify showcase profil.")
    pairs = set()
    for item in evidence:
        if (
            set(item) != {"path", "line", "identifier"}
            or not isinstance(item["line"], int)
            or item["line"] < 1
        ):
            raise ArchifyBuildError("Claude poskytl neplatný důkaz zdroje.")
        if not isinstance(item["identifier"], str) or not item["identifier"]:
            raise ArchifyBuildError("Claude poskytl neplatný identifikátor důkazu.")
        target = _evidence_path(source_root, item["path"])
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise ArchifyBuildError("Důkaz Archify nelze bezpečně přečíst.") from exc
        if item["line"] > len(lines) or item["identifier"] not in lines[item["line"] - 1]:
            raise ArchifyBuildError("Důkaz Archify neodpovídá cestě, řádku nebo identifikátoru.")
        pairs.add((item["path"], item["line"]))
    if not pairs:
        raise ArchifyBuildError("Kandidát Archify nemá žádný ověřený důkaz.")
    for component in components:
        sources = component.get("sources") if isinstance(component, dict) else None
        if not isinstance(sources, list) or not sources:
            raise ArchifyBuildError("Každá komponenta Archify musí mít zdrojový důkaz.")
        for source in sources:
            if (
                not isinstance(source, dict)
                or (source.get("path"), source.get("line")) not in pairs
            ):
                raise ArchifyBuildError("Zdroj komponenty Archify nemá ověřený důkaz.")


def _parse_receipt(raw, command):
    receipt = _json_object(raw, "Původní Archify CLI")
    if receipt.get("ok") is not True or receipt.get("command") != command:
        raise ArchifyBuildError(f"Původní Archify {command} selhal.")
    return receipt


def _validation_summary(receipt):
    validation = receipt.get("validation")
    if isinstance(validation, dict):
        result = validation
    else:
        composition = receipt.get("composition")
        checks = receipt.get("checks")
        result = {
            "checksPassed": sum(1 for item in checks if isinstance(item, dict) and item.get("ok"))
            if isinstance(checks, list)
            else None,
            "checkCount": len(checks) if isinstance(checks, list) else None,
            "compositionProfile": composition.get("profile")
            if isinstance(composition, dict)
            else None,
            "errors": composition.get("summary", {}).get("errors")
            if isinstance(composition, dict)
            else None,
            "warnings": composition.get("summary", {}).get("warnings")
            if isinstance(composition, dict)
            else None,
        }
    if (
        result.get("checksPassed"),
        result.get("checkCount"),
        result.get("compositionProfile"),
        result.get("errors"),
        result.get("warnings"),
    ) != (9, 9, "showcase", 0, 0):
        raise ArchifyBuildError(
            "Původní Archify neprokázal 9 showcase kontrol bez chyb a varování."
        )
    return result


def _receipt_digest(data):
    import hashlib

    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_staged(stage, output_root):
    # stage is a sibling of output_root, so this is one private same-volume
    # directory replacement. It never touches the project's published files.
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ArchifyBuildError("Soukromý výstup Archify musí být prázdný.")
        output_root.rmdir()
    stage.replace(output_root)


def _author(source_root, source_revision, *, deadline, cancel):
    command = _claude_command()
    command[command.index('--max-turns') + 1] = '6'
    raw = _run_process(command, cwd=source_root, env=os.environ.copy(), deadline=deadline,
                       cancel=cancel, stdin=_prompt(source_revision))
    envelope = _json_object(raw, 'Claude')
    if envelope.get('subtype') != 'error_max_turns':
        return raw
    session = envelope.get('session_id')
    if not isinstance(session, str) or not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', session):
        raise ArchifyBuildError('Claude neposkytl bezpečný identifikátor pokračování.')
    final = _claude_command()
    final[final.index('--max-turns') + 1] = '1'
    final[final.index('--tools') + 1] = ''
    final[final.index('--allowedTools') + 1] = ''
    final += ['--resume', session, '--disable-slash-commands']
    return _run_process(final, cwd=source_root, env=os.environ.copy(), deadline=deadline,
                        cancel=cancel, stdin='Exploration is complete. No tools are available now. Emit the final JSON object with candidate, specification, evidence immediately. The candidate MUST be renderable: EVERY component needs explicit numeric pos [x,y] and size [w,h], plus a fitting meta.viewBox, as in the original example. Automatic routes do not place nodes. Prefer 6-8 well-spaced primary components with sparse links and local sources. No invented public meta.repository. Preserve evidence already read. No Markdown fences, no further plan, no requests for tools.')


def _render_candidate(candidate):
    # Původní renderer váže sources na veřejný repozitář. Lokální důkazy mají vlastní sidecar.
    result = copy.deepcopy(candidate)
    result.get('meta', {}).pop('repository', None)
    for component in result.get('components', []):
        component.pop('sources', None)
    return result


def build_archify(
    source_root: Path, output_root: Path, source_revision: str, *, cancel=None
) -> dict:
    """Create a fully verified Archify delivery only inside an empty private root."""
    if not isinstance(source_revision, str) or not REVISION.fullmatch(source_revision):
        raise ArchifyBuildError("Revize zdroje Archify musí být 40znakový lowercase SHA.")
    source_root = _source_root(Path(source_root))
    output_root = Path(output_root)
    if output_root.exists() and (not output_root.is_dir() or any(output_root.iterdir())):
        raise ArchifyBuildError("Soukromý výstup Archify musí být prázdný.")
    if not output_root.parent.is_dir():
        raise ArchifyBuildError("Rodič soukromého výstupu Archify není dostupný.")
    deadline = time.monotonic() + TOTAL_SECONDS
    stage = Path(tempfile.mkdtemp(prefix="archify-private-", dir=output_root.parent))
    try:
        agent_raw = _author(source_root, source_revision, deadline=deadline, cancel=cancel)
        payload = _agent_payload(agent_raw)
        _validate_evidence(source_root, payload["candidate"], payload["evidence"])
        candidate_text = json.dumps(_render_candidate(payload["candidate"]), ensure_ascii=False, indent=2) + "\n"
        candidate = stage / FILES["candidate"]
        candidate.write_text(candidate_text, encoding="utf-8")
        node = shutil.which("node")
        cli = (
            Path(__file__).resolve().parents[1]
            / "vendor"
            / "archify"
            / "archify"
            / "bin"
            / "archify.mjs"
        )
        if not node or not cli.is_file():
            raise ArchifyBuildError("Původní Node CLI Archify není dostupné.")
        common = [node, str(cli)]
        validate = _parse_receipt(
            _run_process(
                [
                    *common,
                    "validate",
                    "architecture",
                    FILES["candidate"],
                    "--quality",
                    "showcase",
                    "--repo-root",
                    str(source_root),
                    "--json",
                ],
                cwd=stage,
                env=_safe_node_env(),
                deadline=deadline,
                cancel=cancel,
            ),
            "validate",
        )
        summary = _validation_summary(validate)
        _write_json(stage / FILES["validate"], validate)
        deliver = _parse_receipt(
            _run_process(
                [
                    *common,
                    "deliver",
                    "architecture",
                    FILES["candidate"],
                    FILES["html"],
                    "--quality",
                    "showcase",
                    "--repo-root",
                    str(source_root),
                    "--json",
                ],
                cwd=stage,
                env=_safe_node_env(),
                deadline=deadline,
                cancel=cancel,
            ),
            "deliver",
        )
        _validation_summary(deliver)
        html_path = stage / FILES["html"]
        if not html_path.is_file() or b"<svg" not in html_path.read_bytes().lower():
            raise ArchifyBuildError("Původní Archify nedoručil SVG HTML artefakt.")
        candidate_bytes, html_bytes = candidate.read_bytes(), html_path.read_bytes()
        if deliver.get("specification") != _receipt_digest(candidate_bytes) or deliver.get(
            "artifact"
        ) != _receipt_digest(html_bytes):
            raise ArchifyBuildError(
                "Potvrzení doručení Archify neodpovídá přesným hashům artefaktů."
            )
        _write_json(stage / FILES["deliver"], deliver)
        visual = _parse_receipt(
            _run_process(
                [*common, "visual-check", FILES["html"], "--json"],
                cwd=stage,
                env=_safe_node_env(),
                deadline=deadline,
                cancel=cancel,
            ),
            "visual-check",
        )
        if (
            visual.get("status") != "pass"
            or visual.get("artifact", {}).get("sha256") != _receipt_digest(html_bytes)["sha256"]
        ):
            raise ArchifyBuildError("Původní Archify visual-check neprokázal doručené HTML.")
        _write_json(stage / FILES["visual"], visual)
        spec = f"# Archify architecture\n\nRevize repa: `{source_revision}`\n\n{payload['specification'].strip()}\n"
        (stage / FILES["spec"]).write_text(spec, encoding="utf-8")
        _write_json(
            stage / FILES["evidence"],
            {"sourceRevision": source_revision, "evidence": payload["evidence"],
             "componentSources": {component['id']: component['sources'] for component in payload['candidate']['components']}},
        )
        _copy_staged(stage, output_root)
        return {
            "sourceRevision": source_revision,
            "outputRoot": str(output_root),
            "fileName": FILES["html"],
            "specificationName": FILES["candidate"],
            "artifact": _receipt_digest(html_bytes),
            "specification": _receipt_digest(candidate_bytes),
            "validation": summary,
            "browserEvidence": {"status": visual.get("status"), "receipt": FILES["visual"]},
            "evidence": FILES["evidence"],
        }
    except ArchifyBuildError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ArchifyBuildError("Soukromé sestavení Archify bezpečně selhalo.") from exc
    finally:
        shutil.rmtree(stage, ignore_errors=True)
