"""Kontrola případů plátna procesu (`cases[]` grafu, `docs/navrhy/2026-11-04-platno-procesu.md` §3).

Případ: `{id, name, description?, start: nodeId, input, env?: {tables?, services?}, expect?: {result?, path?, rows?,
notify?}}`. Volá ho `graph_check` (graf plátna toku) i simulátor (jeden případ z těla).
"""


def _rows_ok(rows):
    return isinstance(rows, list) and all(isinstance(r, dict) for r in rows)


def _tables_ok(tables):
    return isinstance(tables, dict) and all(_rows_ok(rows) for rows in tables.values())


def case_errors(cases, node_ids):
    """Chyby případů česky; `node_ids` jsou id uzlů grafu."""
    if not isinstance(cases, list):
        return ["cases musí být seznam."]
    errors, seen = [], set()
    for case in cases:
        cid = case.get("id") if isinstance(case, dict) else None
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            errors.append(f"Případ {cid!r} nemá jedinečné neprázdné id.")
            continue
        seen.add(cid)
        errors += _case_errors(cid, case, node_ids)
    return errors


def _case_errors(cid, case, node_ids):
    errors = []
    if not isinstance(case.get("name"), str) or not case["name"].strip():
        errors.append(f"Případ {cid} nemá jméno.")
    if not isinstance(case.get("description", ""), str):
        errors.append(f"Případ {cid}: description je text.")
    if case.get("start") not in node_ids:
        errors.append(f"Případ {cid}: start {case.get('start')!r} není uzel grafu.")
    if "input" not in case:
        errors.append(f"Případ {cid}: chybí input (data na startu, klidně {{}}).")
    env, expect = case.get("env", {}), case.get("expect", {})
    if not isinstance(env, dict) or not _tables_ok(env.get("tables", {})) or not isinstance(env.get("services", {}), dict):
        errors.append(f"Případ {cid}: env je {{tables: {{tabulka: [řádky objektů]}}, services: {{uzel: odpověď}}}}.")
    else:
        errors += [f"Případ {cid}: služba {nid!r} není uzel grafu." for nid in env.get("services", {}) if nid not in node_ids]
        errors += [f"Případ {cid}: odpověď služby {nid} s chybou je {{error: text}}." for nid, answer in env.get("services", {}).items()
                   if isinstance(answer, dict) and "error" in answer and not isinstance(answer["error"], str)]
    if not isinstance(expect, dict):
        return errors + [f"Případ {cid}: expect je objekt {{result?, path?, rows?, notify?}}."]
    path = expect.get("path", [])
    if not isinstance(path, list) or not all(isinstance(n, str) for n in path):
        errors.append(f"Případ {cid}: expect.path je seznam id uzlů.")
    else:
        errors += [f"Případ {cid}: expect.path vede přes neexistující uzel {n!r}." for n in path if n not in node_ids]
    if not _tables_ok(expect.get("rows", {})):
        errors.append(f"Případ {cid}: expect.rows je {{tabulka: [řádky objektů]}}.")
    if not isinstance(expect.get("notify", ""), str):
        errors.append(f"Případ {cid}: expect.notify je text.")
    return errors
