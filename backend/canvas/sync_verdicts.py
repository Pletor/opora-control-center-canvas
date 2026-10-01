"""Verdikt Oracle: smí se rozsah commitnout a smí do mainu?

`verdicts_for(state, signals)` skládá z hotového echa (`sync_signals.py`) verdikt podle
částí 4 a 8 kontraktu `docs/synchronizace-pravdy.md`: kontroly brány v pořadí uzlu,
`canCommit`, `canMerge`, blokující echo a jeden krok na každou neprošlou kontrolu.
Nic nečte a nikam nezapisuje; strom skládá podle `parentId`.

Uzel má všech sedm kontrol z části 4. Sektor má vlastní `source`, zelené rozsahy pod
sebou a žádné vysoké echo; oblast jen zelené rozsahy pod sebou. Uzavřený rozsah se
nekontroluje: vrací stav `closed` bez kontrol a bez kroků a pro rodiče se počítá jako
zelený. Kontrola `spec` (zadání je zacommitované) projde, když má rozsah revizi větší
než nula: OporaHub, který by commit zadání držel, zatím neexistuje. Kontrola `docs`
padá u rozsahu, jehož vazba na kód se dotýká rozbitého odkazu — cesta odkazu nebo
samotný dokument leží na vazbě nebo pod ní.
"""

from backend.canvas.sync_signals import TYPES

# Kontroly brány; `children` drží sektor a oblast nad rozsahy pod sebou.
CHECKS = {
    "spec": "Zadání je zacommitované, ne rozepsané",
    "source": "Vazba na kód existuje ve správném druhu",
    "pair": "Pár s touto revizí zadání je v mainu kódu",
    "checks": "U páru je zaznamenaný zelený běh testů",
    "evidence": "Každý krok procesu má důkaz",
    "docs": "Dokumentace dotčených cest nemá rozbitý odkaz",
    "noHighEcho": "Rozsah nemá otevřené echo s vysokou závažností",
    "children": "Všechny rozsahy pod ním jsou zelené",
}

# Echo, které brání i práci ve větvi: vazba rozsahu ukazuje jinam, než kam se sahá.
# Ostatní vysoké echo (zadání napřed, chybějící důkaz, neznámý běh testů) mluví o hotovosti,
# ne o právu pracovat, a blokuje jen merge do mainu.
BLOCKS_COMMIT = ("source-missing", "source-renamed", "closed-area-touched")

# Krok pro kontrolu, jejíž selhání část 7 žádným typem echa nepojmenovává.
_FALLBACK = {"source": "doplň vazbu na kód", "children": "doplň nebo srovnej rozsahy pod ním"}


def verdicts_for(state, signals):
    """Verdikt pro každý rozsah, seřazený podle `id` rozsahu."""
    scopes = state.get("scopes") or []
    children = {}
    for scope in scopes:
        children.setdefault(scope.get("parentId"), []).append(scope)
    # Oblast nikdy není rodičem; členství v ní je dané polohou na plátně, a report ho
    # posílá jako `areaId`. Bez něj by kontrola `children` oblasti neměla co počítat.
    for scope in scopes:
        if scope.get("areaId"):
            children.setdefault(scope["areaId"], []).append(scope)
    mine, pairs, done = _attach(scopes, signals), state.get("pairs") or {}, {}
    for kind in ("node", "sector", "area"):
        # Vnořený sektor se počítá dřív než ten nad ním, jinak by se rodič ptal na potomka,
        # který verdikt ještě nemá, a hlásil by nehotovo i nad samými zelenými rozsahy.
        for scope in sorted(scopes, key=lambda item: -_depth(item, scopes)):
            if scope["kind"] == kind:
                done[scope["id"]] = _verdict(scope, mine[scope["id"]], pairs.get(scope["id"]),
                                             _kids(scope["id"], children), done)
    return [done[key] for key in sorted(done)]


def _depth(scope, scopes):
    """Kolik pater má rozsah nad sebou; vadný graf (kruh) průchod nezacyklí."""
    by_id = {item["id"]: item for item in scopes}
    seen, depth, current = set(), 0, scope.get("parentId")
    while current and current in by_id and current not in seen:
        seen.add(current)
        depth += 1
        current = by_id[current].get("parentId")
    return depth


def _verdict(scope, mine, pair, kids, done):
    reference = {"kind": scope["kind"], "id": scope["id"]}
    if scope.get("closed"):
        return {"scope": reference, "state": "closed", "canCommit": False, "canMerge": False,
                "checks": [], "blocking": [], "nextSteps": []}
    kinds = {signal["type"] for signal in mine}
    high = sorted(signal["type"] for signal in mine if signal["severity"] == "high")
    # Brána uzná pár, jen když je v mainu a sáhl na vlastněnou cestu; podvržený trailer sám nestačí.
    merged = bool((pair or {}).get("mergedToMain") and (pair or {}).get("touchesOwned"))
    checks = _checks_for(scope, kinds, merged, _all_green(kids, done))
    if scope["kind"] != "area":
        checks.append(_check("noHighEcho", not high, high[0] if high else None))
    failed = {check["signal"] for check in checks if not check["passed"]}
    can_merge = all(check["passed"] for check in checks)
    return {
        "scope": reference,
        "state": "green" if can_merge else ("waiting" if merged else "draft"),
        "canCommit": not [signal for signal in mine if signal["type"] in BLOCKS_COMMIT],
        "canMerge": can_merge,
        "checks": checks,
        "blocking": sorted({signal["id"] for signal in mine
                            if signal["severity"] == "high" or signal["type"] in failed}),
        "nextSteps": _steps(checks),
    }


def _checks_for(scope, kinds, merged, kids_green):
    if scope["kind"] == "sector":
        return [_source_check(scope, kinds), _check("children", kids_green)]
    if scope["kind"] != "node":
        return [_check("children", kids_green)]
    return [
        _check("spec", _spec_ready(scope), "opora-uncommitted"),
        _source_check(scope, kinds),
        _check("pair", merged and "spec-ahead" not in kinds, "spec-ahead"),
        _check("checks", scope.get("checksGreen"), "checks-unknown"),
        _check("evidence", scope.get("evidenceComplete"), "evidence-missing"),
        _check("docs", "doc-path-missing" not in kinds, "doc-path-missing"),
    ]


def _spec_ready(scope):
    """Zadání je hotové, když má revizi a ta je zapsaná commitem OporaHubu.

    Report starší než OporaHub `specCommitted` neposílá; tehdy rozhoduje jen revize.
    """
    revision = scope.get("specRevision") or 0
    committed = scope.get("specCommitted")
    return revision > 0 and (committed is None or bool(committed))


def _check(check_id, passed, kind=None):
    return {"id": check_id, "name": CHECKS[check_id], "passed": bool(passed),
            "signal": None if passed else kind}


def _source_check(scope, kinds):
    ref = scope.get("sourceRef") or {}
    if not ref.get("path"):
        return _check("source", False)
    if ref.get("origin") != "existing":
        return _check("source", False, "planned-exists")
    broken = sorted(kinds & {"source-missing", "source-renamed"})
    return _check("source", not broken, broken[0] if broken else None)


def _steps(checks):
    steps = []
    for check in checks:
        if check["passed"]:
            continue
        step = TYPES[check["signal"]][1] if check["signal"] else _FALLBACK.get(check["id"], "")
        if step and step not in steps:
            steps.append(step)
    return steps


def _all_green(kids, done):
    # Prázdná oblast ani prázdný sektor nejsou hotové; nemají co být 1:1.
    if not kids:
        return False
    return all((done.get(kid["id"]) or {}).get("canMerge")
               or (done.get(kid["id"]) or {}).get("state") == "closed" for kid in kids)


def _kids(scope_id, children):
    """Všechny rozsahy pod daným rozsahem, i přes mezistupeň."""
    out = []
    for child in children.get(scope_id, []):
        out.append(child)
        out.extend(_kids(child["id"], children))
    return out


def _attach(scopes, signals):
    """Echo k rozsahu: podle předmětu, u rozbité dokumentace podle dotčené cesty."""
    mine = {scope["id"]: [] for scope in scopes}
    docs = [signal for signal in signals if signal["type"] == "doc-path-missing"]
    for signal in signals:
        owner = signal["subject"]["id"]
        if signal["subject"]["scope"] and owner in mine:
            mine[owner].append(signal)
    for scope in scopes:
        base = (scope.get("sourceRef") or {}).get("path")
        for signal in docs if base else []:
            doc = str(signal["subject"]["id"]).rsplit(":", 1)[0]
            if _under(signal["subject"]["path"], base) or _under(doc, base):
                mine[scope["id"]].append(signal)
    return mine


def _under(path, base):
    return bool(path) and (path == base or path.startswith(base.rstrip("/") + "/"))
