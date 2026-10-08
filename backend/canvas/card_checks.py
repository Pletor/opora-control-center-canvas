"""Declarative task checks; storing a command never executes it."""

import re


def validate_checks(node):
    if not {"checks", "goal_mode"}.intersection(node):
        return
    if node["kind"] != "node":
        raise ValueError("Kontroly a goal_mode patří pouze kartě uzlu.")
    checks = node.get("checks", [])
    if not isinstance(checks, list) or len(checks) > 200:
        raise ValueError("checks musí být pole nejvýše 200 kontrol.")
    seen = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"id", "command"}:
            raise ValueError("Kontrola vyžaduje id a command.")
        identifier, command = check["id"], check["command"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier) or identifier in seen:
            raise ValueError("Kontroly musí mít jedinečná platná ID.")
        seen.add(identifier)
        if not isinstance(command, str) or not command.strip() or len(command) > 4000 or "\x00" in command:
            raise ValueError("Příkaz kontroly musí být neprázdný text do 4000 znaků.")
    if node.get("goal_mode", "manual") not in ("manual", "until_checks_pass"):
        raise ValueError("goal_mode musí být manual nebo until_checks_pass.")
    if node.get("goal_mode") == "until_checks_pass" and not checks:
        raise ValueError("GOAL vyžaduje alespoň jednu strukturovanou kontrolu.")


def checks_passed(node, evidence):
    runs = {run["checkId"]: run for run in (evidence or {}).get("checksRun", [])}
    return all(check["id"] in runs and runs[check["id"]]["command"] == check["command"]
               and runs[check["id"]]["exitCode"] == 0 for check in node.get("checks", []))
