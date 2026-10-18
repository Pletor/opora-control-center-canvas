"""Matematika duelu (docs/schranka-duel.md §2, §3): P(B > A) s rozpadem, vyvrácení, doložení, nezodpovězená otázka,
uznání, remíza, hranice rozhodnutí, totožné claimy, Studentovo t a trend představy."""
import math

import pytest

from backend.editor.brief_vault import brief_vault_duel_math as duel_math
from backend.editor.brief_vault.brief_vault_duel_math import (
    ADOPT_P,
    KEEP_P,
    MAX_ROUNDS,
    MIN_SCORED,
    P0,
    decide,
    duel_probability,
    on_turn,
    rounds,
    student_t_cdf,
    vision_trend,
)

LOGIT_P0 = math.log(0.35 / 0.65)  # = −0.6190392084


def turn(turn_id, side, kind="claim", refs=None, evidence=None, text=None):
    return {
        "id": turn_id, "side": side, "kind": kind, "text": text if text is not None else f"argument {turn_id}",
        "refs": refs or [], "evidence": evidence or [], "by": "agent", "actor": f"actor-{side}",
        "at": "2026-10-15T10:00:00Z",
    }


def score(turn_id, strength, supports, judge="j1", rebutted_by=None, evidence_ok=None):
    entry = {"turnId": turn_id, "judge": judge, "strength": strength, "supports": supports}
    if evidence_ok is not None:
        entry["evidenceOk"] = evidence_ok
    if rebutted_by:
        entry["rebuttedBy"] = rebutted_by
    return entry


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def mirror(turns, scores):
    swap = {"A": "B", "B": "A"}
    return (
        [{**t, "side": swap.get(t["side"], t["side"])} for t in turns],
        [{**s, "supports": swap[s["supports"]]} for s in scores],
    )


def test_constants():
    assert (P0, MAX_ROUNDS, ADOPT_P, KEEP_P, MIN_SCORED) == (0.35, 4, 0.75, 0.40, 3)


def test_without_scores_p_is_p0():
    turns = [turn("b1", "B"), turn("a1", "A"), turn("g1", "A", "grill")]
    result = duel_probability(turns, [])
    assert result["p"] == pytest.approx(0.35, abs=1e-12)
    assert result["logit"] == pytest.approx(LOGIT_P0)
    assert result["n"] == 0 and result["contributions"] == []


def test_hand_example_mean_majority_and_evidence():
    # b1: soudci 8 a 6 pro B → s = 7, w = 1 → +0.7
    # a1: soudce 4 pro A, s doložením → w = 1.5 → −0.4 · 1.5 = −0.6
    # ℓ = −0.6190392 + 0.7 − 0.6 = −0.5190392; P = σ(ℓ) ≈ 0.373077
    turns = [turn("b1", "B"), turn("a1", "A", evidence=[{"source": "a.py:1", "quote": "q"}])]
    scores = [score("b1", 8, "B"), score("b1", 6, "B", judge="j2"), score("a1", 4, "A", evidence_ok=True)]
    result = duel_probability(turns, scores)
    assert result["logit"] == pytest.approx(LOGIT_P0 + 0.1)
    assert result["p"] == pytest.approx(sigmoid(-0.5190392084), abs=1e-9)
    assert result["p"] == pytest.approx(0.373077, abs=1e-6)
    assert result["n"] == 2
    b1, a1 = result["contributions"]
    assert b1 == {"turnId": "b1", "side": "B", "kind": "claim", "strength": 7.0, "weight": 1.0,
                  "delta": pytest.approx(0.7), "reason": "hodnocená výměna"}
    assert a1["weight"] == 1.5 and a1["delta"] == pytest.approx(-0.6)
    assert a1["reason"] == "hodnocená výměna s doložením"


def test_symmetry_mirror_gives_one_minus_p():
    turns = [turn("b1", "B"), turn("a1", "A", evidence=[{"source": "x", "quote": "y"}]),
             turn("g1", "B", "grill"), turn("a2", "A")]
    scores = [score("b1", 9, "B", rebutted_by="a2"), score("a1", 3, "A"), score("g1", 5, "B"), score("a2", 9, "A")]
    p = duel_probability(turns, scores, p0=0.5)["p"]
    m_turns, m_scores = mirror(turns, scores)
    assert duel_probability(m_turns, m_scores, p0=0.5)["p"] == pytest.approx(1 - p, abs=1e-12)
    assert p != pytest.approx(0.5)


def test_rebuttal_needs_stronger_or_equal_rebuttal():
    # b1 s = 6 pro B vyvrácena a2 s = 7 ≥ 6 → w = 0.25 → +0.15; a2 −0.7 → ℓ = logit(p0) − 0.55
    turns = [turn("b1", "B"), turn("a2", "A")]
    strong = duel_probability(turns, [score("b1", 6, "B", rebutted_by="a2"), score("a2", 7, "A")])
    assert strong["contributions"][0]["weight"] == 0.25
    assert strong["contributions"][0]["reason"] == "vyvrácená výměna"
    assert strong["logit"] == pytest.approx(LOGIT_P0 + 0.15 - 0.7)
    # stejná síla 6 ≥ 6 → vyvráceno
    equal = duel_probability(turns, [score("b1", 6, "B", rebutted_by="a2"), score("a2", 6, "A")])
    assert equal["contributions"][0]["weight"] == 0.25
    # slabší vyvrácení 5 < 6 → w zůstává 1 → +0.6 − 0.5
    weak = duel_probability(turns, [score("b1", 6, "B", rebutted_by="a2"), score("a2", 5, "A")])
    assert weak["contributions"][0]["weight"] == 1.0
    assert weak["logit"] == pytest.approx(LOGIT_P0 + 0.1)
    # vyvrácení neohodnocenou výměnou nic neoslabí
    unscored = duel_probability(turns, [score("b1", 6, "B", rebutted_by="a2")])
    assert unscored["contributions"][0]["weight"] == 1.0


def test_rebutted_with_evidence_multiplies():
    # 0.25 · 1.5 = 0.375; b1 s = 8 → +0.3
    turns = [turn("b1", "B", evidence=[{"source": "u", "quote": "q"}]), turn("a2", "A")]
    result = duel_probability(turns, [score("b1", 8, "B", rebutted_by="a2", evidence_ok=True), score("a2", 9, "A")])
    assert result["contributions"][0]["weight"] == pytest.approx(0.375)
    assert result["contributions"][0]["delta"] == pytest.approx(0.3)


def test_concede_blocks_rebuttal():
    # a3 uznává b1 → b1 má w = 1 i přes vyvrácení a2 → +0.6 − 0.7
    turns = [turn("b1", "B"), turn("a2", "A"), turn("a3", "A", "concede", refs=["b1"])]
    result = duel_probability(turns, [score("b1", 6, "B", rebutted_by="a2"), score("a2", 7, "A")])
    b1 = result["contributions"][0]
    assert b1["weight"] == 1.0 and b1["reason"] == "uznaný bod"
    assert result["logit"] == pytest.approx(LOGIT_P0 - 0.1)


def test_judge_tie_contributes_nothing():
    turns = [turn("b1", "B")]
    result = duel_probability(turns, [score("b1", 8, "B"), score("b1", 4, "A", judge="j2")])
    assert result["p"] == pytest.approx(0.35)
    assert result["n"] == 0
    assert result["contributions"][0]["reason"] == "remíza soudců"
    assert result["contributions"][0]["delta"] == 0


def test_unanswered_grill_counts_against_asked_side():
    # B položila g1 na A, A neodpověděla; soudci 6 a 8 → s = 7 proti A → +0.7 (i když soudci psali supports A)
    turns = [turn("g1", "B", "grill")]
    result = duel_probability(turns, [score("g1", 6, "A"), score("g1", 8, "A", judge="j2")])
    assert result["contributions"][0]["reason"] == "nezodpovězená otázka"
    assert result["logit"] == pytest.approx(LOGIT_P0 + 0.7)
    assert result["n"] == 1
    # grill A na B bez odpovědi → proti B → −0.5
    against_b = duel_probability([turn("g2", "A", "grill")], [score("g2", 5, "B")])
    assert against_b["logit"] == pytest.approx(LOGIT_P0 - 0.5)
    # bez skóre nic
    assert duel_probability(turns, [])["contributions"] == []


def test_answered_grill_counts_by_its_score():
    # A odpověděla na g1 → g1 se počítá podle většiny soudců: 6 pro A → −0.6
    turns = [turn("g1", "B", "grill"), turn("x1", "A", "answer", refs=["g1"])]
    result = duel_probability(turns, [score("g1", 6, "A")])
    assert result["contributions"][0]["reason"] == "hodnocená výměna"
    assert result["logit"] == pytest.approx(LOGIT_P0 - 0.6)
    # odpověď od nesprávné strany (B sama sobě) otázku nezodpoví
    wrong = [turn("g1", "B", "grill"), turn("x1", "B", "answer", refs=["g1"])]
    assert duel_probability(wrong, [score("g1", 6, "A")])["contributions"][0]["reason"] == "nezodpovězená otázka"


def test_human_grill_side_from_refs():
    # člověk se ptá na výměnu A → grill míří na A; nezodpovězená, s = 4 → +0.4
    turns = [turn("a1", "A"), turn("h1", "human", "grill", refs=["a1"])]
    result = duel_probability(turns, [score("h1", 4, "B")])
    assert result["contributions"][0]["reason"] == "nezodpovězená otázka"
    assert result["logit"] == pytest.approx(LOGIT_P0 + 0.4)
    assert on_turn(turns) == [{"side": "A", "grillId": "h1"}]
    # bez jasné strany (žádné refs, nebo obě strany) → přeskočí s důvodem, n = 0
    for refs in ([], ["a1", "b1"]):
        unclear = [turn("a1", "A"), turn("b1", "B"), turn("h1", "human", "grill", refs=refs)]
        res = duel_probability(unclear, [score("h1", 9, "B")])
        assert res["contributions"][0]["reason"] == "otázka bez jasné strany"
        assert res["p"] == pytest.approx(0.35) and res["n"] == 0
        assert on_turn(unclear) == []


def test_scores_for_unknown_turns_are_ignored():
    assert duel_probability([turn("b1", "B")], [score("zz", 9, "B")])["contributions"] == []


def test_on_turn_and_rounds():
    turns = [
        turn("g1", "A", "grill"), turn("g2", "B", "grill"), turn("x1", "B", "answer", refs=["g1"]),
        turn("g3", "A", "grill"), turn("n1", "human", "note"),
    ]
    assert on_turn(turns) == [{"side": "A", "grillId": "g2"}, {"side": "B", "grillId": "g3"}]
    assert rounds(turns, "A") == 2 and rounds(turns, "B") == 1 and rounds(turns, "human") == 0


@pytest.mark.parametrize(
    ("p", "n", "outcome"),
    [
        (0.75, 3, "adopt"),
        (0.7499, 3, "synthesis"),
        (0.9, 2, "synthesis"),  # n < MIN_SCORED
        (0.40, 0, "keep"),
        (0.4001, 5, "synthesis"),
        (0.1, 10, "keep"),
    ],
)
def test_decide_boundaries(p, n, outcome):
    result = decide({"p": p, "n": n}, open_grills=0, rounds_exhausted=False)
    assert result["outcome"] == outcome and result["reason"]


def test_decide_waits_for_open_grills_unless_rounds_exhausted():
    assert decide({"p": 0.9, "n": 5}, open_grills=1, rounds_exhausted=False)["outcome"] is None
    assert decide({"p": 0.9, "n": 5}, open_grills=1, rounds_exhausted=True)["outcome"] == "adopt"


@pytest.mark.parametrize(
    ("t", "df", "expected", "tol"),
    [
        (0.0, 5, 0.5, 1e-12),
        (1.0, 1, 0.75, 1e-9),
        (2.015048, 5, 0.95, 1e-6),
        (-2.570582, 5, 0.025, 1e-6),
        (2.015, 5, 0.95, 1e-4),
        (-2.571, 5, 0.025, 1e-4),
        (1.697261, 30, 0.95, 1e-6),
        (3.0, 2, 0.5 + 3 / (2 * math.sqrt(11)), 1e-9),  # df = 2: F = ½ + t / (2√(t² + 2))
        (-7.5, 1, 0.5 + math.atan(-7.5) / math.pi, 1e-9),  # df = 1: F = ½ + atan(t)/π
        (1e8, 1, 0.5 + math.atan(1e8) / math.pi, 1e-12),  # asymptotický chvost
        (-1e9, 3, 0.0, 1e-12),
    ],
)
def test_student_t_cdf_known_values(t, df, expected, tol):
    assert student_t_cdf(t, df) == pytest.approx(expected, abs=tol)


def points(scores):
    return [{"score": s, "at": f"2026-10-{i + 1:02d}"} for i, s in enumerate(scores)]


def test_trend_rising_hand_example():
    # y = 1,3,2,4; x̄ = 1.5, Σ(x−x̄)² = 5, β̂ = 4/5 = 0.8; rezidua −0.3, 0.9, −0.9, 0.3 → SSE = 1.8
    # s² = 1.8/2 = 0.9; se = √(0.9/5) = 0.424264; t = 1.885618; df = 2 → F = ½ + t/(2√(t²+2)) = 0.9
    result = vision_trend(points([1, 3, 2, 4]))
    assert result["slope"] == pytest.approx(0.8)
    assert result["se"] == pytest.approx(math.sqrt(0.18))
    assert result["p"] == pytest.approx(0.9, abs=1e-9)
    assert result["n"] == 4 and result["last"] == 4.0 and result["state"] == "approaching"


def test_trend_falling_is_mirror():
    result = vision_trend(points([4, 2, 3, 1]))
    assert result["slope"] == pytest.approx(-0.8)
    assert result["p"] == pytest.approx(0.1, abs=1e-9)
    assert result["state"] == "receding"


def test_trend_flat_with_noise_is_unclear():
    result = vision_trend(points([5, 6, 6, 5]))
    assert result["slope"] == pytest.approx(0.0, abs=1e-12)
    assert result["p"] == pytest.approx(0.5, abs=1e-9)
    assert result["state"] == "unclear"


def test_trend_insufficient_data():
    for data in ([], [5], [5, 7]):
        result = vision_trend(points(data))
        assert result["p"] is None and result["slope"] is None and result["se"] is None
        assert result["state"] == "insufficient" and result["n"] == len(data)
    assert vision_trend(points([5, 7]))["last"] == 7.0
    assert vision_trend([])["last"] is None


def test_trend_zero_se_uses_sign_of_slope():
    up = vision_trend(points([1, 2, 3, 4]))
    assert up["se"] == 0.0 and up["p"] == 1.0 and up["state"] == "approaching"
    down = vision_trend(points([9, 7, 5]))
    assert down["se"] == 0.0 and down["p"] == 0.0 and down["state"] == "receding"
    flat = vision_trend(points([5, 5, 5]))
    assert flat["se"] == 0.0 and flat["p"] == 0.5 and flat["state"] == "unclear"


def test_trend_uses_last_window_points():
    # prvních 5 bodů klesá, posledních 8 přesně roste → okno 8 vidí jen růst
    result = vision_trend(points([10, 9, 8, 7, 6, 1, 2, 3, 4, 5, 6, 7, 8]))
    assert result["n"] == 8 and result["slope"] == pytest.approx(1.0) and result["p"] == 1.0
    assert vision_trend(points([1, 3, 2, 4, 9]), window=4)["n"] == 4


def test_evidence_bonus_needs_majority_of_judges_with_evidence_ok():
    turns = [turn("b1", "B", evidence=[{"source": "a.py:1", "quote": "q"}])]
    unchecked = duel_probability(turns, [score("b1", 10, "B")])
    assert unchecked["contributions"][0]["weight"] == 1.0
    split = duel_probability(turns, [score("b1", 10, "B", evidence_ok=True), score("b1", 10, "B", "j2", evidence_ok=False)])
    assert split["contributions"][0]["weight"] == 1.0  # remíza není většina
    ok = duel_probability(turns, [score("b1", 10, "B", evidence_ok=True), score("b1", 10, "B", "j2", evidence_ok=True),
                                  score("b1", 10, "B", "j3")])
    assert ok["contributions"][0]["weight"] == 1.5


def test_concede_counts_only_from_opposite_side():
    turns = [turn("b1", "B"), turn("a2", "A"), turn("b3", "B", "concede", refs=["b1"])]
    result = duel_probability(turns, [score("b1", 6, "B", rebutted_by="a2"), score("a2", 7, "A")])
    assert result["contributions"][0]["reason"] == "vyvrácená výměna"


def test_claims_over_limit_do_not_move_p():
    three = [turn(f"b{i}", "B") for i in range(3)]
    five = [turn(f"b{i}", "B") for i in range(5)]
    scores = [score(f"b{i}", 10, "B") for i in range(5)]
    capped = duel_probability(five, scores)
    assert capped["p"] == pytest.approx(duel_probability(three, scores)["p"]) and capped["n"] == 3
    assert capped["contributions"][-1]["reason"] == "nad mez claim"


PROOF = [{"source": "docs/a.md:3", "quote": "incidenty"}, {"source": "https://example.org/b", "quote": "data"}]


def same_claim(turn_id, side="B", text="Slabá hesla jsou zdroj incidentů.", evidence=PROOF, by="agent", at="t1"):
    return {**turn(turn_id, side, text=text, evidence=[dict(item) for item in evidence]), "by": by, "at": at}


def test_identical_claims_count_once():
    one = duel_probability([same_claim("b1")], [score("b1", 8, "B")])
    copies = [same_claim("b1"), same_claim("b2", by="jiny", at="t2"), same_claim("b3", by="treti", at="t3")]
    three = duel_probability(copies, [score(f"b{i}", 8, "B") for i in (1, 2, 3)])
    assert three["p"] == pytest.approx(one["p"]) and three["n"] == one["n"] == 1
    first, *rest = three["contributions"]
    assert first["turnId"] == "b1" and first["reason"] == "hodnocená výměna"
    assert [(item["turnId"], item["delta"], item["reason"]) for item in rest] == [
        ("b2", 0, "opakovaný totožný argument"), ("b3", 0, "opakovaný totožný argument")]


def test_fingerprint_ignores_evidence_order_and_outer_or_repeated_whitespace():
    base = duel_math.claim_fingerprint(same_claim("b1"))
    assert duel_math.claim_fingerprint(same_claim("b2", evidence=PROOF[::-1])) == base
    assert duel_math.claim_fingerprint(same_claim("b3", text="  Slabá   hesla jsou\tzdroj\n incidentů. ")) == base
    assert duel_math.claim_fingerprint(same_claim("b4", text="slabá hesla jsou zdroj incidentů.")) != base
    assert duel_math.claim_fingerprint(same_claim("b5", text="Slaba hesla jsou zdroj incidentu.")) != base
    assert duel_math.claim_fingerprint(same_claim("b6", evidence=PROOF[:1])) != base
    assert duel_math.claim_fingerprint(same_claim("b7", evidence=[])) != base
    assert duel_math.claim_fingerprint(same_claim("b8", evidence=[])) == duel_math.claim_fingerprint(same_claim("b9", evidence=[]))
    assert duel_math.claim_fingerprint(same_claim("a1", side="A")) != base


def test_case_or_diacritics_differ_and_still_count():
    turns = [same_claim("b1"), same_claim("b2", text="SLABÁ hesla jsou zdroj incidentů."),
             same_claim("b3", text="Slaba hesla jsou zdroj incidentu.")]
    result = duel_probability(turns, [score(f"b{i}", 8, "B") for i in (1, 2, 3)])
    assert result["n"] == 3 and all(item["reason"] == "hodnocená výměna" for item in result["contributions"])


def test_truly_different_claims_still_count():
    turns = [same_claim("b1"), same_claim("b2", text="Jiný důvod."), same_claim("b3", evidence=PROOF[:1])]
    result = duel_probability(turns, [score(f"b{i}", 8, "B") for i in (1, 2, 3)])
    assert result["n"] == 3 and result["logit"] == pytest.approx(LOGIT_P0 + 3 * 0.8)


def test_same_claim_on_both_sides_are_two_exchanges():
    turns = [same_claim("b1"), same_claim("a1", side="A")]
    result = duel_probability(turns, [score("b1", 8, "B"), score("a1", 6, "A")])
    assert result["n"] == 2 and result["logit"] == pytest.approx(LOGIT_P0 + 0.8 - 0.6)


def test_legacy_duplicates_read_first_occurrence_and_ignore_duplicate_scores():
    # Uložená historie s duplikáty (stav přímo v datech): platí první výskyt v turns, skóre duplikátu se ignoruje.
    turns = [same_claim("b1"), same_claim("b2", evidence=PROOF[::-1], text=" Slabá hesla jsou zdroj incidentů.")]
    result = duel_probability(turns, [score("b2", 10, "B"), score("b1", 4, "B")])
    assert result["n"] == 1 and result["logit"] == pytest.approx(LOGIT_P0 + 0.4)
    assert [(item["turnId"], item["delta"], item["reason"]) for item in result["contributions"]] == [
        ("b1", pytest.approx(0.4), "hodnocená výměna"), ("b2", 0, "opakovaný totožný argument")]


def test_duplicate_score_is_not_used_as_rebuttal():
    # b2 = kopie b1 se silným skóre; a1 vyvrací odkazem na kopii. Kopie se čte jako b1 (síla 5 < 7), a1 vyvrácená není.
    claim_a = same_claim("a1", side="A", text="Heslo stačí.")
    copy = [same_claim("b1"), same_claim("b2", by="jiny"), claim_a]
    scores = [score("b1", 5, "B"), score("b2", 10, "B", judge="j2"), score("a1", 7, "A", rebutted_by="b2")]
    plain = duel_probability([same_claim("b1"), claim_a], [score("b1", 5, "B"), score("a1", 7, "A", rebutted_by="b1")])
    result = duel_probability(copy, scores)
    assert result["p"] == pytest.approx(plain["p"]) and result["n"] == plain["n"] == 2
    assert result["contributions"][-1]["reason"] == "hodnocená výměna"


@pytest.mark.parametrize("strength", [None, "silné", [1]])
def test_duplicate_with_broken_score_does_not_crash(strength):
    one = duel_probability([same_claim("b1")], [score("b1", 8, "B")])
    broken = {"turnId": "b2", "judge": "j2", "strength": strength, "supports": "B"}
    result = duel_probability([same_claim("b1"), same_claim("b2")], [score("b1", 8, "B"), broken])
    assert result["p"] == pytest.approx(one["p"]) and result["n"] == 1


@pytest.mark.parametrize("conceded", ["b1", "b2"])
def test_refs_to_copy_point_to_first_occurrence(conceded):
    # Uznání kopie = uznání prvního claimu: výsledek nezávisí na tom, které z totožných id strana zvolí.
    turns = [same_claim("b1"), same_claim("b2"), same_claim("a1", side="A", text="Námitka."),
             turn("a2", "A", "concede", refs=[conceded])]
    scores = [score("b1", 6, "B", rebutted_by="a1"), score("a1", 8, "A")]
    result = duel_probability(turns, scores)
    first = result["contributions"][0]
    assert first["turnId"] == "b1" and first["reason"] == "uznaný bod" and first["weight"] == 1.0


@pytest.mark.parametrize("left, right", [
    ({"evidence": None}, {"evidence": []}),
    ({"evidence": None}, {"evidence": "chybí"}),
    ({"evidence": [{"source": "a.py:1", "quote": None}]}, {"evidence": [{"source": "a.py:1", "quote": ""}]}),
    ({"evidence": [{"source": "a.py:1", "quote": "q"}] * 2}, {"evidence": [{"source": "a.py:1", "quote": "q"}]}),
    ({"evidence": ["text", 3, None, {"source": ["x"], "quote": "q"}]}, {"evidence": []}),
    ({"text": "Slabá\u00a0hesla"}, {"text": "Slabá hesla"}),
])
def test_fingerprint_is_robust_for_legacy_data(left, right):
    base = {"id": "b1", "side": "B", "kind": "claim", "text": "Slabá hesla", "evidence": []}
    first, second = {**base, **left}, {**base, **right}
    if second.get("evidence") == "chybí":
        second.pop("evidence")
    assert duel_math.claim_fingerprint(first) == duel_math.claim_fingerprint(second)
    result = duel_probability([first, {**second, "id": "b2"}], [score("b1", 8, "B"), score("b2", 8, "B")])
    assert result["n"] == 1


def test_zero_width_space_is_not_whitespace():
    base = {"id": "b1", "side": "B", "kind": "claim", "text": "Slabá hesla", "evidence": []}
    assert duel_math.claim_fingerprint(base) != duel_math.claim_fingerprint({**base, "text": "Slabá\u200bhesla"})
