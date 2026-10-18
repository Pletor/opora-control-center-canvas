"""Matematika duelu Schránky (docs/schranka-duel.md §2, §3).

Čisté funkce bez I/O: `duel_probability` počítá P(B > A) z výměn a skóre soudců (§3.1), `decide` z ní odvodí
výsledek (§3.2), `vision_trend` trend shody s představou přes Studentovo t (§3.3), `on_turn` a `rounds` říkají,
kdo je na tahu a kolik kol strana odehrála (§2). Jen stdlib `math`.

Upřesnění kontraktu, která tu platí:
- Strana výměny se určuje většinou soudců (`supports`); při remíze výměna nepřispívá (`reason: "remíza soudců"`).
- `grill` míří na opačnou stranu než autor. `grill` od `human` nebo `judge` míří na stranu, na jejíž výměny odkazuje
  (`refs`); když odkazuje na obě nebo na žádnou, nemá jasnou stranu a přeskočí se s důvodem.
- Nezodpovězená `grill` se skóre přispěje proti straně, které byla položena, silou průměru soudců (§2, §3.1);
  bez skóre nepřispěje nic. Zodpovězená `grill` se počítá normálně podle svého skóre.
- `concede` na výměnu X: strana bod uznala, takže X má váhu 1 bez vyvrácení (`rebuttedBy` ji už neoslabí);
  doložení (`evidence`) ji dál násobí. Uznání platí jen od protistrany uznané výměny (vlastní strana se nepočítá).
- Bonus doložení ×1.5 platí, jen když většina soudců výměny dala ve skóre `evidenceOk: true` (doklad ověřili).
- Strana má nejvýš `MAX_CLAIMS` výměn `claim`; další (kdyby se do stavu dostaly) se nepočítají (`reason: "nad mez claim"`).
- Totožný `claim` (`claim_fingerprint`: strana, text se sjednocenými bílými znaky, množina doložení) se počítá jen
  poprvé v pořadí `turns`; opakování má `delta` 0 (`reason: "opakovaný totožný argument"`), jeho skóre se vyřadí
  ze všech výpočtů (i jako vyvrácení) a nejde do `n` ani do meze claim. Odkazy na kopii (`refs`, `rebuttedBy`)
  míří na první výskyt. Není to sémantická deduplikace ani doklad nezávislosti.
"""

import math

P0 = 0.35
MAX_ROUNDS = 4
MAX_CLAIMS = 3
ADOPT_P, KEEP_P, MIN_SCORED = 0.75, 0.40, 3
REBUTTED_WEIGHT, EVIDENCE_FACTOR = 0.25, 1.5

_SIDES = ("A", "B")
_OTHER = {"A": "B", "B": "A"}
_SE_ZERO = 1e-12
_SIMPSON_STEPS = 4000
_ASYMPTOTIC_T = 1e7
_DUPLICATE = "opakovaný totožný argument"
_NOT_SCORED = ("remíza soudců", "otázka bez jasné strany", "nad mez claim", _DUPLICATE)


def _evidence_pairs(evidence) -> frozenset:
    """Množina (source, quote); chybějící nebo ne-seznam = prázdná, ne-dict či nehashovatelné položky se přeskočí,
    quote None ≡ ""."""
    pairs = set()
    for item in evidence if isinstance(evidence, list) else []:
        if not isinstance(item, dict):
            continue
        pair = (item.get("source"), "" if item.get("quote") is None else item.get("quote"))
        try:
            hash(pair)
        except TypeError:
            continue
        pairs.add(pair)
    return frozenset(pairs)


def claim_fingerprint(turn: dict) -> tuple:
    """Otisk claimu: strana, text po strip a sjednocení každé sekvence bílých znaků (`str.split`, tedy i NBSP;
    zero-width znaky jako U+200B ne) do mezery, velikost písmen i diakritika zůstávají, a množina dvojic
    (source, quote) doložení. Autor, id, čas a refs nerozhodují."""
    text = " ".join(str(turn.get("text") or "").split())
    return turn.get("side"), text, _evidence_pairs(turn.get("evidence"))


def _canonical(turns: list[dict]) -> dict:
    """id výměny → id prvního výskytu totožného claimu (ostatní výměny samy na sebe)."""
    first: dict[tuple, str] = {}
    canon = {}
    for turn in turns:
        key = claim_fingerprint(turn) if turn.get("kind") == "claim" else ("turn", turn.get("id"))
        canon[turn.get("id")] = first.setdefault(key, turn.get("id"))
    return canon


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _scores_by_turn(scores: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for score in scores:
        grouped.setdefault(score.get("turnId"), []).append(score)
    return grouped


def _mean_strength(entries: list[dict]) -> float:
    return sum(float(entry.get("strength", 0)) for entry in entries) / len(entries)


def _majority_sign(entries: list[dict]) -> int:
    votes_b = sum(1 for entry in entries if entry.get("supports") == "B")
    votes_a = sum(1 for entry in entries if entry.get("supports") == "A")
    return (votes_b > votes_a) - (votes_b < votes_a)


def _grill_target(turn: dict, by_id: dict[str, dict]) -> str | None:
    """Strana, které byla `grill` položena; None = bez jasné strany."""
    side = turn.get("side")
    if side in _OTHER:
        return _OTHER[side]
    targets = {by_id[ref].get("side") for ref in turn.get("refs") or [] if ref in by_id}
    targets &= set(_SIDES)
    return targets.pop() if len(targets) == 1 else None


def _is_answered(grill: dict, target: str, turns: list[dict]) -> bool:
    return any(
        turn.get("kind") == "answer" and turn.get("side") == target and grill.get("id") in (turn.get("refs") or [])
        for turn in turns
    )


def _open_grills(turns: list[dict]) -> list[dict]:
    by_id = {turn.get("id"): turn for turn in turns}
    result = []
    for turn in turns:
        if turn.get("kind") != "grill":
            continue
        target = _grill_target(turn, by_id)
        if target is not None and not _is_answered(turn, target, turns):
            result.append({"side": target, "grillId": turn.get("id")})
    return result


def _contribution(turn: dict, strength: float, sign: int, weight: float, reason: str) -> dict:
    return {
        "turnId": turn.get("id"),
        "side": turn.get("side"),
        "kind": turn.get("kind"),
        "strength": strength,
        "weight": weight,
        "delta": sign * (strength / 10.0) * weight,
        "reason": reason,
    }


def duel_probability(turns: list[dict], scores: list[dict], p0: float = P0) -> dict:
    """P(B > A) = σ(logit(p0) + Σ sign·(s/10)·w) s rozpadem příspěvků (§3.1)."""
    canon = _canonical(turns)
    duplicates = {turn_id for turn_id, first in canon.items() if first != turn_id}
    turns = [{**turn, "refs": [canon.get(ref, ref) for ref in turn.get("refs") or []]} for turn in turns]
    scores = [{**entry, "rebuttedBy": canon.get(entry["rebuttedBy"], entry["rebuttedBy"])}
              if entry.get("rebuttedBy") else entry for entry in scores]
    with_scores = {entry.get("turnId") for entry in scores}
    by_id = {turn.get("id"): turn for turn in turns}
    grouped = _scores_by_turn([entry for entry in scores if entry.get("turnId") not in duplicates])
    conceded = {
        ref for turn in turns if turn.get("kind") == "concede" for ref in turn.get("refs") or []
        if ref in by_id and _OTHER.get(by_id[ref].get("side")) == turn.get("side")
    }
    claims: dict[str, int] = {}
    contributions: list[dict] = []
    for turn in turns:
        if turn.get("id") in duplicates:
            if turn.get("id") in with_scores:
                contributions.append(_contribution(turn, 0.0, 0, 0.0, _DUPLICATE))
            continue
        entries = grouped.get(turn.get("id"))
        if not entries:
            continue
        strength = _mean_strength(entries)
        if turn.get("kind") == "claim":
            claims[turn.get("side")] = claims.get(turn.get("side"), 0) + 1
            if claims[turn.get("side")] > MAX_CLAIMS:
                contributions.append(_contribution(turn, strength, 0, 0.0, "nad mez claim"))
                continue
        verified = sum(1 for entry in entries if entry.get("evidenceOk") is True) * 2 > len(entries)
        evidence = EVIDENCE_FACTOR if turn.get("evidence") and verified else 1.0
        if turn.get("kind") == "grill":
            target = _grill_target(turn, by_id)
            if target is None:
                contributions.append(_contribution(turn, strength, 0, 0.0, "otázka bez jasné strany"))
                continue
            if not _is_answered(turn, target, turns):
                sign = 1 if target == "A" else -1
                contributions.append(_contribution(turn, strength, sign, evidence, "nezodpovězená otázka"))
                continue
        sign = _majority_sign(entries)
        if sign == 0:
            contributions.append(_contribution(turn, strength, 0, 0.0, "remíza soudců"))
            continue
        weight, reason = 1.0, "hodnocená výměna"
        if turn.get("id") in conceded:
            reason = "uznaný bod"
        else:
            rebuttals = {entry.get("rebuttedBy") for entry in entries if entry.get("rebuttedBy")}
            if any(grouped.get(ref) and _mean_strength(grouped[ref]) >= strength for ref in rebuttals):
                weight, reason = REBUTTED_WEIGHT, "vyvrácená výměna"
        if evidence != 1.0:
            reason += " s doložením"
        contributions.append(_contribution(turn, strength, sign, weight * evidence, reason))
    logit = _logit(p0) + sum(item["delta"] for item in contributions)
    scored = sum(1 for item in contributions if item["reason"] not in _NOT_SCORED)
    return {"p": _sigmoid(logit), "logit": logit, "n": scored, "contributions": contributions}


def decide(probability: dict, open_grills: int, rounds_exhausted: bool) -> dict:
    """Výsledek duelu podle §3.2; outcome None = ještě nelze rozhodnout."""
    if open_grills > 0 and not rounds_exhausted:
        return {"outcome": None, "reason": f"otevřené otázky: {open_grills}"}
    p, n = probability["p"], probability["n"]
    if p >= ADOPT_P and n >= MIN_SCORED:
        return {"outcome": "adopt", "reason": f"P = {p:.3f} ≥ {ADOPT_P} a n = {n} ≥ {MIN_SCORED}"}
    if p <= KEEP_P:
        return {"outcome": "keep", "reason": f"P = {p:.3f} ≤ {KEEP_P}"}
    if p >= ADOPT_P:
        return {"outcome": "synthesis", "reason": f"P = {p:.3f} ≥ {ADOPT_P}, ale n = {n} < {MIN_SCORED}"}
    return {"outcome": "synthesis", "reason": f"{KEEP_P} < P = {p:.3f} < {ADOPT_P}"}


def on_turn(turns: list[dict]) -> list[dict]:
    """Otevřené `grill`, na které musí strana odpovědět."""
    return _open_grills(turns)


def rounds(turns: list[dict], side: str) -> int:
    """Počet kol strany = počet `grill`, které strana položila."""
    return sum(1 for turn in turns if turn.get("kind") == "grill" and turn.get("side") == side)


def student_t_cdf(t: float, df: float) -> float:
    """Distribuční funkce Studentova t. Simpson přes hustotu po substituci x = √ν·tan θ,

    kde hustota·dx = Γ((ν+1)/2) / (√π·Γ(ν/2)) · cos^(ν−1) θ dθ (hladká na omezeném intervalu);
    pro |t| > 1e7 asymptotický chvost c·ν^((ν+1)/2)·|t|^(−ν)/ν.
    """
    if t == 0:
        return 0.5
    nu = float(df)
    log_c = math.lgamma((nu + 1) / 2) - math.lgamma(nu / 2) - 0.5 * math.log(nu * math.pi)
    a = abs(t)
    if a > _ASYMPTOTIC_T:
        tail = math.exp(log_c + (nu + 1) / 2 * math.log(nu) - nu * math.log(a)) / nu
        half = 0.5 - tail
    else:
        upper = math.atan(a / math.sqrt(nu))
        k = math.exp(log_c + 0.5 * math.log(nu))
        h = upper / _SIMPSON_STEPS
        total = 1.0 + math.cos(upper) ** (nu - 1)
        for i in range(1, _SIMPSON_STEPS):
            total += (4 if i % 2 else 2) * math.cos(i * h) ** (nu - 1)
        half = k * total * h / 3
    return 0.5 + half if t > 0 else 0.5 - half


def vision_trend(points: list[dict], window: int = 8) -> dict:
    """Trend shody s představou: OLS sklon posledních `window` bodů, P(β > 0) = T_{n−2}(β̂/se) (§3.3)."""
    recent = points[-window:] if window > 0 else []
    ys = [float(point["score"]) for point in recent]
    n = len(ys)
    last = ys[-1] if ys else None
    if n < 3:
        return {"p": None, "slope": None, "se": None, "n": n, "last": last, "state": "insufficient"}
    x_mean = (n - 1) / 2
    y_mean = sum(ys) / n
    sxx = sum((x - x_mean) ** 2 for x in range(n))
    slope = sum((x - x_mean) * (y - y_mean) for x, y in enumerate(ys)) / sxx
    intercept = y_mean - slope * x_mean
    sse = sum((y - (intercept + slope * x)) ** 2 for x, y in enumerate(ys))
    se = math.sqrt(max(sse, 0.0) / (n - 2) / sxx)
    if se < _SE_ZERO:
        se = 0.0
        p = 1.0 if slope > _SE_ZERO else 0.0 if slope < -_SE_ZERO else 0.5
    else:
        p = student_t_cdf(slope / se, n - 2)
    state = "approaching" if p >= 0.7 else "receding" if p <= 0.3 else "unclear"
    return {"p": p, "slope": slope, "se": se, "n": n, "last": last, "state": state}
