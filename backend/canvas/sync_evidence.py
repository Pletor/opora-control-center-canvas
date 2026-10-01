"""Důkazy z vnějšího světa pro Oracle: git, disk, registr a dokumentace.

Modul jen čte. Sbírá to, co `sync_report.py` potřebuje, aby mohl složit stav světa:
revizi mainu, poslední commity, stav cest na disku, pracovní prostory z registru
a rozbité odkazy v dokumentaci. Nic nepočítá a nic nehodnotí; hodnocení dělá
`sync_signals.py` nad hotovými daty.
"""

from backend.integrations import git_read

COMMIT_LIMIT = 50


def main_head(root):
    """Revize mainu; když projekt main nemá, bere se aktuální revize."""
    if root is None:
        return None
    return git_read.head(root, "refs/heads/main") or git_read.head(root)


def commits_in_main(root, head, limit=COMMIT_LIMIT):
    """Poslední commity mainu ve tvaru, kterému rozumí `commit_pairs`."""
    if root is None or head is None:
        return []
    found = []
    for sha in git_read.recent(root, head, limit):
        info = git_read.commit_info(root, sha)
        if info is None:
            continue
        found.append({
            "sha": info["sha"],
            "branches": ["main"],
            "paths": info["paths"],
            "trailers": info["trailers"],
            "task": None,
            "inMain": True,
            "date": info["date"],
        })
    return found


def path_facts(sources, root, scopes):
    """Pro každou cestu z vazeb: existuje, jaký je to druh a kam byla přejmenována."""
    facts = {}
    for scope in scopes:
        path = (scope.get("sourceRef") or {}).get("path")
        if not path or path in facts:
            continue
        facts[path] = _fact(sources, root, path)
    return facts


def _fact(sources, root, path):
    if root is None:
        return {"exists": False, "kind": None, "renamedTo": None}
    try:
        target = sources.target(root, path)
        kind = "directory" if target.is_dir() else "file" if target.is_file() else None
    except (FileNotFoundError, OSError, ValueError):
        kind = None
    if kind is not None:
        return {"exists": True, "kind": kind, "renamedTo": None}
    return {"exists": False, "kind": None, "renamedTo": git_read.rename_of(root, path)}


def workspaces_from(rows, root, head):
    """Pracovní prostory z už přečtených řádků registru i s tím, zda jejich základ leží v mainu.

    Řádky si volající čte sám pod zámkem služby; tady se sahá jen na git, který je pomalý
    a zámek by držel zbytečně dlouho.
    """
    found = []
    for row in rows:
        base = row["base_sha"]
        in_main = bool(root and base and head and git_read.is_ancestor(root, base, head))
        found.append({
            "id": row["id"],
            "nodeId": row["node_id"],
            "branch": row["branch"],
            "baseSha": base,
            "baseInMain": in_main,
        })
    return found


def doc_issues(root):
    """Odkazy v dokumentaci projektu, které nevedou na existující cestu."""
    if root is None:
        return []
    # Kontrola odkazů je nástroj, ne prostředí; import až tady, aby na něm backend nestál.
    from tools.doc_check import check_repo

    try:
        return check_repo(root)
    except OSError:
        return []
