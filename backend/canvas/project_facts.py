"""Card references resolve to the existing project settings, without copying values."""

import re


def validate_fact_refs(node):
    if "factRefs" not in node:
        return
    refs = node["factRefs"]
    if node["kind"] not in ("node", "sector") or not isinstance(refs, list) or len(refs) > 500:
        raise ValueError("factRefs musí být pole nejvýše 500 odkazů na kartě nebo sektoru.")
    if any(not isinstance(ref, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", ref) for ref in refs) or len(set(refs)) != len(refs):
        raise ValueError("Odkazy na fakta musí být jedinečná platná ID nastavení.")


def resolve_facts(node, settings):
    by_id = {setting["id"]: setting for setting in settings}
    return [{"id": ref, "key": by_id[ref]["key"], "value": by_id[ref]["value"], "missing": False}
            if ref in by_id else {"id": ref, "key": "", "value": "", "missing": True}
            for ref in node.get("factRefs", [])]
