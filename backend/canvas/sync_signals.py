"""Echo Oracle: nerovnosti mezi zadáním, kódem a důkazy jako čistá data.

Modul nic nečte a nikam nezapisuje. `evaluate(state)` dostane celý svět od volajícího
(rozsahy, stav cest v gitu, páry, commity bez páru, pracovní prostory a rozbité odkazy
v dokumentaci) a vrátí `{"signals": [...], "verdicts": [...]}`; verdikt brány počítá
`sync_verdicts.py`. Typy echa, jejich závažnost a akci, která je uzavře, drží část 7
kontraktu `docs/synchronizace-pravdy.md`. `id` echa je prvních 16 znaků SHA-256
z `typ|kanonický předmět`, takže stejná nerovnost má napříč běhy stejné `id` a jde ji
odložit. Pořadí je pevné: echo podle typu a `id`, verdikty podle `id` rozsahu.

Meze tohoto kroku: echo `opora-uncommitted` se
počítá podle `specCommitted` z reportu. Sem ale zatím
nepatří `task-desync` a `closed-area-touched`. Uzavřený rozsah (`closed`) se
nekontroluje: nevydá žádné echo, jen verdikt se stavem `closed`.
"""

import hashlib
import json
from datetime import UTC, datetime

# Závažnost a akce, která echo uzavře; oba sloupce z části 7 kontraktu.
TYPES = {
    "spec-ahead": ("high", "zadej práci; uzavře ji nový pár"),
    "code-unclaimed": ("medium", "přiřaď k zadání, nebo označ jako údržbu"),
    "source-missing": ("high", "oprav vazbu nebo obnov soubor"),
    "source-renamed": ("medium", "potvrď přesun"),
    "planned-exists": ("low", "přepni návrh na existující zdroj"),
    "duplicate-path": ("medium", "sluč nebo zpřesni"),
    "checks-unknown": ("high", "spusť testy a zapiš výsledek"),
    "doc-path-missing": ("medium", "oprav odkaz nebo dokument zruš"),
    "base-stale": ("medium", "rebase, nebo nové zadání"),
    "opora-uncommitted": ("low", "potvrď commit"),
    "workspace-orphan": ("low", "ukliď nebo obnov"),
}


def evaluate(state):
    """Vrátí `{"signals": [...], "verdicts": [...]}` pro celý projekt."""
    # Import až tady: verdikty stojí na tabulce typů výše, tabulka na nich ne.
    from backend.canvas.sync_verdicts import verdicts_for

    signals = collect(state)
    return {"signals": signals, "verdicts": verdicts_for(state, signals)}


def collect(state):
    """Seřazené echo pro celý projekt; uzavřené rozsahy se přeskakují."""
    scopes = state.get("scopes") or []
    paths, pairs = state.get("paths") or {}, state.get("pairs") or {}
    live = [scope for scope in scopes if not scope.get("closed")]
    out = []
    for scope in live:
        _source_echo(scope, paths, state, out)
        pair = pairs.get(scope["id"])
        _spec_echo(scope, pair, state, out)
        if (scope.get("specRevision") or 0) > 0 and scope.get("specCommitted") is False:
            out.append(_echo("opora-uncommitted",
                             _subject(scope["kind"], scope["id"], None, scope["specRevision"]),
                             f"revize {scope['specRevision']} má commit OporaHubu",
                             "zadání je jen rozepsané", "OporaHub", state))
        # Běh testů se ptá jen uzlu: sektor a oblast mají podle části 4
        # kontrakt postavený na rozsazích pod sebou, ne na vlastním důkazu.
        if scope["kind"] != "node" or not (pair or {}).get("mergedToMain"):
            continue
        subject = _subject(scope["kind"], scope["id"], None, scope.get("specRevision"))
        if not scope.get("checksGreen"):
            out.append(_echo("checks-unknown", subject, "zelený běh testů u páru",
                             "běh testů není zaznamenaný", "pár rozsahu", state))
    _duplicate_echo(live, state, out)
    _world_echo(state, {scope["id"] for scope in scopes}, out)
    unique = {}
    for signal in out:
        unique.setdefault(signal["id"], signal)
    return sorted(unique.values(), key=lambda signal: (signal["type"], signal["id"]))


def _subject(scope=None, ident=None, path=None, revision=None):
    return {"scope": scope, "id": ident, "path": path, "specRevision": revision}


def _echo(kind, subject, expected, actual, source, state):
    subject = dict(subject)  # každé echo drží vlastní předmět, ať se dva nesdílí
    body = json.dumps(subject, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    severity, action = TYPES[kind]
    return {
        "id": hashlib.sha256(f"{kind}|{body}".encode()).hexdigest()[:16],
        "type": kind, "severity": severity, "subject": subject,
        "evidence": {"expected": expected, "actual": actual, "source": source},
        "observedAt": state.get("observedAt"), "gitHead": state.get("gitHead"), "action": action,
    }


def _moment(value):
    """ISO řetězec jako datum bez časové zóny; None i nesmysl vrací None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _source_echo(scope, paths, state, out):
    ref = scope.get("sourceRef") or {}
    path = ref.get("path")
    if not path:
        return
    info = paths.get(path) or {}
    subject = _subject(scope["kind"], scope["id"], path, scope.get("specRevision"))
    if ref.get("origin") == "planned":
        if info.get("exists"):
            out.append(_echo("planned-exists", subject, "navrhovaná cesta v gitu ještě není",
                             f"{path} už existuje", "git", state))
        return
    wanted = ref.get("kind")
    if info.get("exists") and (wanted is None or info.get("kind") == wanted):
        return
    if info.get("renamedTo"):
        out.append(_echo("source-renamed", subject, f"{path} v gitu",
                         f"přejmenováno na {info['renamedTo']}", "git", state))
        return
    out.append(_echo("source-missing", subject, f"{path} jako {wanted or 'cesta'}",
                     f"v gitu chybí (druh: {info.get('kind')})", "git", state))


def _spec_echo(scope, pair, state, out):
    """Zadání je napřed, dokud kód neukáže, že plní jeho revizi.

    Trailer ve zprávě commitu je autoritativní, protože revizi říká přímo. Bez traileru
    rozhoduje čas: pár v mainu musí být novější než uložené zadání. Commit s datem
    v budoucnosti se za důkaz nebere — jinak by stačilo posunout hodiny.
    """
    revision = scope.get("specRevision") or 0
    if revision <= 0:
        return
    if pair is None:
        actual = "pár chybí"
    elif pair.get("revisionInCode") is not None:
        if pair["revisionInCode"] >= revision:
            return
        actual = f"poslední pár nese revizi {pair['revisionInCode']}"
    else:
        last, observed = _moment(pair.get("lastCommitAt")), _moment(state.get("observedAt"))
        if last is None:
            actual = "pár nemá commit v mainu"
        elif observed is not None and last > observed:
            actual = f"commit má datum v budoucnosti ({pair.get('lastCommitAt')})"
        elif not _older(last, _moment(scope.get("specSavedAt"))):
            return
        else:
            actual = f"pár je starší než zadání ({pair.get('lastCommitAt')})"
    source = f"pár {pair.get('oporaCommit')}" if pair else "páry rozsahu"
    out.append(_echo("spec-ahead", _subject(scope["kind"], scope["id"], None, revision),
                     f"revize {revision}", actual, source, state))


def _older(commit_at, saved_at):
    return bool(commit_at and saved_at and commit_at < saved_at)


def _duplicate_echo(scopes, state, out):
    seen = {}
    for scope in scopes:
        path = (scope.get("sourceRef") or {}).get("path")
        if path:
            seen.setdefault(path, []).append(scope["id"])
    for path in sorted(seen):
        owners = seen[path]
        if len(owners) > 1:
            out.append(_echo("duplicate-path", _subject(None, None, path, None),
                             "jedna karta na cestu", f"rozsahy: {', '.join(sorted(owners))}",
                             "graf", state))


def _world_echo(state, known, out):
    """Echo, které nepatří jednomu rozsahu: commity, pracovní prostory, dokumentace."""
    for commit in state.get("unclaimedCommits") or []:
        sha = commit.get("sha")
        out.append(_echo("code-unclaimed", _subject(None, sha, None, None),
                         "commit v mainu má pár",
                         f"bez páru, sahá do {len(commit.get('paths') or [])} cest",
                         f"git {sha}", state))
    for space in state.get("workspaces") or []:
        subject = _subject(None, space.get("id"), None, None)
        source = f"pracovní prostor {space.get('id')}"
        if not space.get("baseInMain", True):
            out.append(_echo("base-stale", subject, "základ větve je předkem mainu",
                             f"větev {space.get('branch')} stojí mimo main", source, state))
        if space.get("nodeId") not in known:
            out.append(_echo("workspace-orphan", subject, "prostor patří rozsahu v grafu",
                             f"rozsah {space.get('nodeId')} v grafu není", source, state))
    for node_id in state.get("orphanSpecs") or []:
        # Zadání smazaného uzlu zůstává v databázi. Uzel se stejným id by ho tiše zdědil,
        # proto se hlásí stejně jako osiřelý pracovní prostor.
        out.append(_echo("workspace-orphan", _subject(None, node_id, None, None),
                         "zadání patří rozsahu v grafu",
                         f"zadání rozsahu {node_id} v grafu není",
                         f"zadání {node_id}", state))
    for issue in state.get("docIssues") or []:
        where = f"{issue.get('doc')}:{issue.get('line')}"
        out.append(_echo("doc-path-missing", _subject(None, where, issue.get("path"), None),
                         f"{issue.get('path')} existuje", "cesta v gitu chybí", where, state))
