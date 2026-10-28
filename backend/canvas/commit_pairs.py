"""Spáruje rozsah práce v OPORA (oblast, sektor, uzel) s commity v gitu podle dodaných důkazů.

Modul je čistý: nic nečte ani nezapisuje, git ani databázi nevolá. Všechna data dodá volající.
Kontrakt je popsaný v `docs/synchronizace-pravdy.md`, část 6 „Párování commitů“.
"""

from datetime import UTC, datetime

# Důkazy od nejsilnějšího po nejslabší; `evidence` páru je první z nich, který u commitů padl.
EVIDENCE_ORDER = ("trailer", "branch", "task", "paths")
CONFIDENCE = {"trailer": "strong", "branch": "strong", "task": "strong", "paths": "weak"}

# Trailer, kterým si tým dobrovolně píše rozsah a revizi zadání do zprávy commitu.
TRAILER_KEY = "Opora-Node"


def _segments(path):
    """Cesta rozpadlá na segmenty přes `/`; prázdné segmenty (dvojí nebo koncové `/`) zahodí."""
    if not isinstance(path, str):
        return ()
    return tuple(part for part in path.split("/") if part)


def _covers(owned, touched):
    """Adresář pokrývá své potomky: `backend/canvas` ano `…/x.py`, ne `backend/canvas-old/x.py`."""
    if not owned:
        return False
    return touched[: len(owned)] == owned


def owned_paths(scope_id, nodes):
    """Cesty, které rozsah vlastní: jeho vlastní `sourceRef.path` a cesty všech potomků v grafu.

    `nodes` je seznam uzlů grafu (`{"id", "parentId", "kind", "sourceRef"}`). Vadný graf
    (uzel sám sobě rodičem, kruh mezi uzly) průchod nezacyklí, výsledek je bez duplicit a seřazený.
    """
    children = {}
    by_id = {}
    for node in nodes or ():
        by_id[node.get("id")] = node
        children.setdefault(node.get("parentId"), []).append(node.get("id"))
    reached = {scope_id}
    queue = [scope_id]
    while queue:
        for child_id in children.get(queue.pop(), ()):
            if child_id in reached:
                continue
            reached.add(child_id)
            queue.append(child_id)
    paths = set()
    for node_id in reached:
        source_ref = (by_id.get(node_id) or {}).get("sourceRef") or {}
        path = source_ref.get("path")
        if isinstance(path, str) and path.strip():
            paths.add(path)
    return sorted(paths)


def _trailer_values(commit):
    values = (commit.get("trailers") or {}).get(TRAILER_KEY)
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    return tuple(values)


def _trailer_match(commit, scope_id):
    """Řekne, zda trailer commitu míří na rozsah, a jakou nejvyšší revizi u něj hlásí."""
    matched = False
    revision = None
    for value in _trailer_values(commit):
        name, separator, raw = str(value).partition("@")
        if name.strip() != scope_id:
            continue
        matched = True
        if not separator:  # `Opora-Node: <id>` bez revize: commit karty, revizi nehlásí
            continue
        try:
            number = int(raw.strip())
        except ValueError:
            continue
        revision = number if revision is None else max(revision, number)
    return matched, revision


def _evidence_of(commit, scope_id, scope_task, branch, owned):
    """Množina důkazů, kterými se commit hlásí k rozsahu, plus revize z jeho traileru."""
    found = set()
    matched, revision = _trailer_match(commit, scope_id)
    if matched:
        found.add("trailer")
    if branch and branch in (commit.get("branches") or ()):
        found.add("branch")
    if scope_task and commit.get("task") == scope_task:
        found.add("task")
    touched = [_segments(path) for path in (commit.get("paths") or ())]
    if any(_covers(own, one) for own in owned for one in touched):
        found.add("paths")
    return found, revision


def _moment(value):
    """ISO 8601 jako porovnatelný okamžik; čas bez zóny bereme jako UTC. Nečitelné datum → None."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _latest(dates):
    """Nejnovější datum ze seznamu; když se žádné nedá přečíst, rozhodne pořadí řetězců."""
    if not dates:
        return None
    readable = [(moment, value) for value in dates if (moment := _moment(value)) is not None]
    return max(readable)[1] if readable else max(dates)


def pair_for_scope(*, scope, spec_revision, spec_saved_at, workspace, commits, owned):
    """Spočte pár rozsahu s commity: které to jsou, jak silný je důkaz a co z nich plyne.

    `spec_saved_at` patří do kontraktu volajícího (kdy bylo zadání uloženo), na tvar páru nemá vliv.
    """
    scope_id = (scope or {}).get("id")
    scope_task = (scope or {}).get("task")
    branch = (workspace or {}).get("branch")
    owned_segments = [own for own in (_segments(path) for path in owned or ()) if own]

    shas, seen = [], set()
    strengths = set()
    touches_owned = False
    revision_in_code = None
    merged_to_main = False
    main_dates = []
    commit_task = None
    for commit in commits or ():
        found, revision = _evidence_of(commit, scope_id, scope_task, branch, owned_segments)
        if not found:
            continue
        sha = commit.get("sha")
        if sha not in seen:
            seen.add(sha)
            shas.append(sha)
        strengths |= found
        # Důkaz pro bránu je jen commit, který skutečně sáhl na vlastněnou cestu. Samotný
        # trailer ve zprávě by jinak stačil k tomu, aby rozsah zezelenal bez řádky kódu.
        if "paths" in found and commit.get("inMain"):
            touches_owned = True
        # Revizi z traileru bereme jen od commitu, který se rozsahu skutečně dotkl: cestou,
        # nebo větví jeho pracovního prostoru. Zprávu commitu si pisatel určuje sám.
        if revision is not None and {"paths", "branch"} & found:
            known = revision_in_code
            revision_in_code = revision if known is None else max(known, revision)
        if commit_task is None and commit.get("task"):
            commit_task = commit["task"]
        if commit.get("inMain"):
            merged_to_main = True
            if commit.get("date"):
                main_dates.append(commit["date"])

    evidence = next((name for name in EVIDENCE_ORDER if name in strengths), "none")
    confidence = CONFIDENCE.get(evidence, "none")
    if evidence == "trailer" and not {"paths", "branch"} & strengths:
        # Trailer, který se nekříží s cestou ani s větví, je tvrzení, ne důkaz.
        confidence = "weak"
    return {
        "scope": scope,
        "specRevision": int(spec_revision or 0),
        "gitCommits": shas,
        "branch": branch,
        "task": scope_task or commit_task,
        "evidence": evidence,
        "confidence": confidence,
        "revisionInCode": revision_in_code,
        "mergedToMain": merged_to_main,
        "touchesOwned": touches_owned,
        "lastCommitAt": _latest(main_dates),
    }
