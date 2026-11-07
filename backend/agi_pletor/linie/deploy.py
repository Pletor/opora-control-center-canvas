"""Nasazení jako událost (docs/navrhy/2026-11-06-linie-rebrand.md §5, §5a), ne tag: `<data>/projects/<p>/linie/deploy.json`.

Událost `{env, sha, repo, at, by, origin}`. `origin: 'environment'` zapisuje token brány nebo agent nasazovacího skriptu
(`by = agent:<jméno>`), `origin: 'human'` je zápis člověka z Velína („hlášeno člověkem“, nikdy potvrzení prostředí).
Kdo smí do kterého prostředí, říká `opora.local.toml`:

    [linie.deploy]
    production = ["agent:deploy"]           # identita: "human" nebo "agent:<jméno>"
    preview = ["agent:deploy", "human"]

Bez souboru nebo sekce nesmí nikdo (403 `deploy_not_allowed`).
"""
import tomllib
from pathlib import Path

from backend.agi_pletor.linie import jsonfile
from backend.brain_opora.determinism.gate_payloads import GateError


def _path(data_root, project):
    return Path(data_root) / "projects" / project / "linie" / "deploy.json"


def allowed(config_path):
    """`{env: [identity]}` z `[linie.deploy]`; chyba nebo chybějící sekce = nic."""
    try:
        section = tomllib.loads(Path(config_path).read_text(encoding="utf-8")).get("linie", {}).get("deploy", {})
    except (OSError, ValueError):
        return {}
    return {env: who for env, who in section.items() if isinstance(who, list)} if isinstance(section, dict) else {}


def read(data_root, project):
    found = jsonfile.read(_path(data_root, project), [])
    return [e for e in found if isinstance(e, dict) and e.get("env")] if isinstance(found, list) else []


def record(data_root, project, config_path, env, sha, repo, by, at):
    """Zapíše událost, když `by` smí do `env`; `sha` je už ověřené plné sha."""
    if by not in allowed(config_path).get(env, []):
        raise GateError(403, "deploy_not_allowed", f"{by} nesmí zapisovat nasazení do prostředí {env}.",
                        "Povolení je v opora.local.toml [linie.deploy].")
    event = {"env": env, "sha": sha, "repo": str(repo), "at": at, "by": by,
             "origin": "human" if by == "human" else "environment"}
    jsonfile.update(_path(data_root, project), [], lambda events: [*events, event])
    return event


def latest(events):
    """Poslední událost každého prostředí: `{env: {sha, at, origin, by}}`."""
    return {e["env"]: {key: e.get(key) for key in ("sha", "at", "origin", "by")} for e in events}
