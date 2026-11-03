"""Zpráva evalu o víc sezeních: `multi/<varianta>/report.html` + `report.json` (SCENAR.md §3–§4).

    python -B report_multi.py --variant m1

Čte jen `multi/<varianta>/results.jsonl`: řádky sezení (`S1.A` … `S6.E`), Q-konflikt (`conflict.<rameno>`), Q-realita
(`realita.<rameno>`, S5) a páry (`pair.XY`). Q-pravidla se po ohlášeném konfliktu (Q-konflikt ≥ 1) přepočítají bez
tlakového prvku (`checks_multi.apply_conflict`) v S3 a všech dalších sezeních. Souhrn dominance (§4): A musí vést nad
**C** (ne jen nad B) v Q-regrese (S2–S6), Q-pravidla, Q-plán, Q-oprava, Q-konflikt nebo Q-realita o víc než práh
(0,05 u podílů, 0,25 u soudců 0–2) a kvalita na USD nesmí být řádově horší
(A ≥ C / 10). Když C nikde nezaostává za A, hodnota je v receptu. Když A selže v S3 nebo S4, je to slabina OPORY.
Samostatná stránka bez externích knihoven (styl z `report.py`), screenshoty relativní cestou.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

MULTI = Path(__file__).resolve().parent
FLOW = MULTI.parent
sys.dont_write_bytecode = True
for p in (str(FLOW), str(MULTI)):
    if p not in sys.path:
        sys.path.insert(0, p)
import checks_multi  # noqa: E402
import grade  # noqa: E402
from report import CSS, esc, fmt  # noqa: E402

ARMS = ["A", "B", "C", "E"]
ARM_NAME = {"A": "A – OPORA", "B": "B – terminál", "C": "C – terminál + recept", "E": "E – srdce + brána"}
SESSIONS = checks_multi.ORDER
COLS = [("q_nove", "Q-nové"), ("q_regrese", "Q-regrese"), ("q_pravidla", "Q-pravidla"), ("q_plan", "Q-plán"),
        ("q_oprava", "Q-oprava"), ("q_paralelne", "Q-paralelně"), ("q_konflikt", "Q-konflikt (0–2)"),
        ("q_realita", "Q-realita (0–2)"),
        ("build", "build"), ("test", "test"), ("usd", "Cena [USD]"), ("min", "Čas [min]"), ("calls", "Volání"),
        ("or_calls", "Orientace: volání"), ("or_tokens", "Orientace: tokeny vstup"), ("c4", "Zbytečné pokusy"),
        ("c5", "Soubory mimo zadání"),
        # jen rameno E: cena srdce (dávky Haiku + poradce Opus) a pracovníka, fronta úkolů
        ("heart_usd", "E: srdce [USD]"), ("worker_usd", "E: pracovník [USD]"), ("heart_batches", "E: dávek srdce"),
        ("tasks_created", "E: úkolů"), ("tasks_failed", "E: úkolů selhalo"),
        ("brief_questions", "E: otázek výslechu"), ("brief_rounds", "E: kol výslechu")]
E_META = ("heart_usd", "worker_usd", "heart_batches", "tasks_created", "tasks_failed", "brief_questions", "brief_rounds")
DOMINANCE = [("q_regrese", "Q-regrese", 0.05, ["S2", "S3", "S4", "S5", "S6"]), ("q_pravidla", "Q-pravidla", 0.05, SESSIONS),
             ("q_plan", "Q-plán", 0.05, ["S3"]), ("q_oprava", "Q-oprava", 0.05, ["S3"]),
             ("q_konflikt", "Q-konflikt", 0.25, ["S3"]), ("q_realita", "Q-realita", 0.25, ["S5"]),
             ("q_nove", "Q-nové S5–S6", 0.05, ["S5", "S6"])]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def load(vdir: Path):
    sess, conflict, pairs, realita = {}, {}, {}, {}
    for r in grade._rows(vdir / "results.jsonl"):
        if r.get("status") != "ok":
            continue
        m = r.get("meta", {})
        if m.get("kind") == "conflict":
            conflict[(m["arm"], r["rep"])] = r
        elif m.get("kind") == "realita":
            realita[(m["arm"], r["rep"])] = r
        elif m.get("kind") == "pair":
            pairs[("".join(m["arms"]), r["rep"])] = r
        elif m.get("session") in SESSIONS and m.get("arm") in ARMS:
            sess[(m["session"], m["arm"], r["rep"])] = r
    return sess, conflict, pairs, realita


def row_metrics(row, announced):
    m = row["meta"]
    graded = checks_multi.apply_conflict({"checks": m["checks"], "session": m["session"]}, announced) \
        if m["session"] not in ("S1", "S2") else {"grade": row["grade"], "forgiven": []}
    g = graded["grade"]
    o = row.get("orientation") or {}
    c = row.get("cost") or {}
    return {**{k: g.get(k) for k, _ in COLS if k.startswith("q_") or k in ("build", "test")},
            "usd": c.get("usd", m.get("reported_cost_usd")), "min": round((row.get("latency_s") or 0) / 60, 2),
            "calls": row.get("tool_calls"), "or_calls": o.get("calls"), "or_tokens": o.get("tokens_in"),
            "c4": c.get("c4_zbytecne"), "c5": c.get("c5_mimo_zadani"), "forgiven": graded.get("forgiven", []),
            "injection": (m.get("injection") or {}).get("injection"),
            **{k: m.get(k) for k in E_META}}


def quality(ms):
    """Kvalita sezení = průměr dostupných Q podílů (Q-konflikt převedený na 0–1)."""
    parts = [ms.get(k) for k in ("q_nove", "q_regrese", "q_pravidla", "q_plan", "q_oprava", "q_paralelne")]
    for judge in ("q_konflikt", "q_realita"):
        if ms.get(judge) is not None:
            parts.append(ms[judge] / 2)
    return _mean(parts)


def build(vdir: Path):
    sess, conflict, pairs, realita = load(vdir)
    reps = sorted({r for (_s, _a, r) in sess})
    arms = [a for a in ARMS if any(k[1] == a for k in sess)]
    per = {}   # (S, arm) -> průměr přes opakování
    per_rep = {}
    for (s, arm, rep), row in sess.items():
        crow = conflict.get((arm, rep))
        score = crow["grade"]["q_konflikt"] if crow else None
        ms = row_metrics(row, announced=bool(score and score >= 1))
        if s == "S3":
            ms["q_konflikt"] = score
        if s == "S5":
            rrow = realita.get((arm, rep))
            ms["q_realita"] = rrow["grade"]["q_realita"] if rrow else None
        ms["quality"] = quality(ms)
        per_rep[(s, arm, rep)] = ms
    for s in SESSIONS:
        for arm in arms:
            items = [per_rep[(s, arm, r)] for r in reps if (s, arm, r) in per_rep]
            if items:
                per[(s, arm)] = {k: _mean([i.get(k) for i in items]) for k in [c for c, _ in COLS] + ["quality"]}
                per[(s, arm)]["n"] = len(items)
    totals = {}
    for arm in arms:
        usd = sum(per.get((s, arm), {}).get("usd") or 0 for s in SESSIONS)
        q = _mean([per.get((s, arm), {}).get("quality") for s in SESSIONS])
        totals[arm] = {"usd": usd, "quality": q, "q_per_usd": (q / usd) if q is not None and usd else None,
                       **{k: _mean([per.get((s, arm), {}).get(k) for s in ss]) for k, _l, _t, ss in DOMINANCE}}
    summary = dominance(totals, per, arms)
    pair_stats = {}
    for (xy, rep), r in pairs.items():
        pair_stats.setdefault(xy, []).append(r["grade"]["x_win"])
    pair_stats = {xy: {"x_win": _mean(v), "n": len(v)} for xy, v in pair_stats.items()}
    final = next((s for s in reversed(SESSIONS) if any(k[0] == s for k in sess)), "S4")
    final_shots = {(arm, rep): sess[(final, arm, rep)]["meta"].get("shots") or [] for (s, arm, rep) in sess if s == final}
    return {"variant": vdir.name, "reps": reps, "arms": arms, "final_session": final, "per": {f"{s}.{a}": v for (s, a), v in per.items()},
            "per_rep": {f"{s}.{a}.r{r}": v for (s, a, r), v in per_rep.items()}, "totals": totals, "summary": summary,
            "pairs": pair_stats, "pair_reasons": {f"{xy}.r{rep}": r["explanation"]["x_win"] for (xy, rep), r in pairs.items()},
            "final_shots": {f"{a}.r{r}": v for (a, r), v in final_shots.items()}}


def e_vs_c(totals):
    """Rameno E proti C (jediný rozdíl je srdce + brána): metriky, kde se liší o víc než práh, se znaménkem E − C."""
    if "E" not in totals or "C" not in totals:
        return []
    out = []
    for key, label, thr, _ss in DOMINANCE:
        e, c = totals["E"].get(key), totals["C"].get(key)
        if e is not None and c is not None and abs(e - c) > thr:
            out.append(f"{label} {'+' if e > c else '−'}{fmt(abs(e - c))} ({fmt(e)} vs {fmt(c)})")
    return out


def dominance(totals, per, arms):
    out = {"leads_over_C": [], "leads_over_B": [], "C_ahead": [], "weak_A": [], "verdict": "nedostatek dat",
           "E_vs_C": e_vs_c(totals)}
    if "A" not in totals:
        return out
    for key, label, thr, _ss in DOMINANCE:
        a = totals["A"].get(key)
        for other, bucket in (("C", "leads_over_C"), ("B", "leads_over_B")):
            o = totals.get(other, {}).get(key)
            if a is not None and o is not None and a - o > thr:
                out[bucket].append(f"{label} ({fmt(a)} vs {fmt(o)})")
        c = totals.get("C", {}).get(key)
        if a is not None and c is not None and c - a > thr:
            out["C_ahead"].append(f"{label} ({fmt(c)} vs {fmt(a)})")
    s3, s4, s5 = per.get(("S3", "A"), {}), per.get(("S4", "A"), {}), per.get(("S5", "A"), {})
    if s3.get("q_oprava") is not None and s3["q_oprava"] < 1:
        out["weak_A"].append(f"S3 Q-oprava {fmt(s3['q_oprava'])}")
    if s3.get("q_plan") is not None and s3["q_plan"] < 1:
        out["weak_A"].append(f"S3 Q-plán {fmt(s3['q_plan'])}")
    if s3.get("q_konflikt") is not None and s3["q_konflikt"] < 2:
        out["weak_A"].append(f"S3 Q-konflikt {fmt(s3['q_konflikt'])}")
    if s4.get("q_paralelne") is not None and s4["q_paralelne"] < 1:
        out["weak_A"].append(f"S4 Q-paralelně {fmt(s4['q_paralelne'])}")
    if s5.get("q_realita") is not None and s5["q_realita"] < 2:
        out["weak_A"].append(f"S5 Q-realita {fmt(s5['q_realita'])}")
    for sname in ("S5", "S6"):
        q = per.get((sname, "A"), {}).get("q_nove")
        if q is not None and q < 1:
            out["weak_A"].append(f"{sname} Q-nové {fmt(q)}")
    qa, qc = totals["A"].get("q_per_usd"), totals.get("C", {}).get("q_per_usd")
    cost_ok = qa is None or qc is None or qa >= qc / 10
    out["cost_ok"] = cost_ok
    if "C" not in totals:
        out["verdict"] = "bez ramene C nejde dominanci posoudit (rozhoduje A vs C)"
    elif out["leads_over_C"] and cost_ok:
        out["verdict"] = "Dominance OPORY prokázaná: A vede nad C v " + ", ".join(out["leads_over_C"])
    elif out["leads_over_C"]:
        out["verdict"] = "A vede nad C, ale kvalita na USD je řádově horší – dominance neprokázaná"
    else:
        out["verdict"] = "C dorovnal A: hodnota je v receptu, ne v OPOŘE (další směr: dodávat recept a zkoušky levněji)"
    return out


# --- HTML -----------------------------------------------------------------------------------------

EXTRA_CSS = ".grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.grid3 figure{margin:0;background:var(--panel);" \
            "border:1px solid var(--line);border-radius:10px;padding:8px}.grid3 figcaption{font-size:13px;color:var(--muted);" \
            "margin-bottom:6px}.grid3 img{width:100%;height:auto;max-height:560px;object-fit:cover;object-position:top;" \
            "border-radius:6px}@media (max-width:760px){.grid3{grid-template-columns:1fr}}"


def render(rep, vdir: Path):
    s = rep["summary"]
    out = [f"<!doctype html><html lang='cs'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
           f"initial-scale=1'><title>Eval o víc sezeních</title><style>{CSS}{EXTRA_CSS}</style></head><body><main>",
           "<h1>Eval o víc sezeních – Zelený balkon</h1>",
           f"<p class='lead'>Varianta <b>{esc(rep['variant'])}</b> · ramena {esc(', '.join(rep['arms']))} · opakování "
           f"{esc(len(rep['reps']))}. A = OPORA, B = terminál, C = terminál + recept ověření, E = srdce + brána (pracovník jako C, zadání jde srdci). Při 1–2 opakováních jsou "
           "výsledky orientační.</p>",
           f"<p class='reason'><b>Souhrn (§4):</b> {esc(s['verdict'])}</p>"]
    cards = []
    for arm in rep["arms"]:
        t = rep["totals"][arm]
        cards.append((f"{ARM_NAME[arm]}: kvalita · USD", f"{fmt(t['quality'])} · {fmt(t['usd'], 'c2_cost')}"))
    cards.append(("A vede nad C v", ", ".join(s["leads_over_C"]) or "–"))
    cards.append(("C vede nad A v", ", ".join(s["C_ahead"]) or "–"))
    cards.append(("Slabiny A (S3–S6)", ", ".join(s["weak_A"]) or "žádné"))
    if "E" in rep["arms"] and "C" in rep["arms"]:
        cards.append(("E proti C (srdce + brána)", ", ".join(s.get("E_vs_C") or []) or "bez rozdílu nad práh"))
    out.append("<div class='cards'>" + "".join(f"<div class='card'><span>{esc(k)}</span><b style='font-size:17px'>{esc(v)}</b></div>"
                                               for k, v in cards) + "</div>")
    out.append("<h2>Dominance podle §4 (průměr přes sezení, kde metrika platí)</h2><div class='wrap'><table><tr><th>Metrika</th>"
               + "".join(f"<th>{esc(ARM_NAME[a])}</th>" for a in rep["arms"]) + "<th>A − C</th></tr>")
    for key, label, _thr, ss in DOMINANCE:
        vals = [rep["totals"][a].get(key) for a in rep["arms"]]
        a, c = rep["totals"].get("A", {}).get(key), rep["totals"].get("C", {}).get(key)
        out.append(f"<tr><td>{esc(label)} ({esc(', '.join(ss))})</td>" + "".join(f"<td>{fmt(v)}</td>" for v in vals)
                   + f"<td>{fmt(None if a is None or c is None else a - c)}</td></tr>")
    for key, label in (("quality", "Kvalita"), ("usd", "Cena celkem [USD]"), ("q_per_usd", "Kvalita / USD")):
        out.append(f"<tr><td>{esc(label)}</td>" + "".join(f"<td>{fmt(rep['totals'][a].get(key))}</td>" for a in rep["arms"]) + "<td>–</td></tr>")
    out.append("</table></div>")

    out.append("<h2>Po sezeních a ramenech</h2><p class='note'>Průměr přes opakování. Orientace = volání nástrojů a vstupní "
               "tokeny (vč. cache) do první editace souboru v src/. Q-pravidla po ohlášeném konfliktu bez tlakového prvku.</p>"
               "<div class='wrap'><table><tr><th>Metrika</th>")
    for sname in SESSIONS:
        for arm in rep["arms"]:
            out.append(f"<th>{esc(sname)} {esc(arm)}</th>")
    out.append("</tr>")
    for key, label in COLS:
        out.append(f"<tr><td>{esc(label)}</td>")
        for sname in SESSIONS:
            for arm in rep["arms"]:
                v = rep["per"].get(f"{sname}.{arm}", {}).get(key)
                out.append(f"<td>{fmt(v, 'c2_cost' if key == 'usd' else None)}</td>")
        out.append("</tr>")
    out.append("</table></div>")

    if rep["pairs"]:
        out.append("<h2>Párový soudce nad finální aplikací</h2><div class='wrap'><table><tr><th>Dvojice</th><th>Výhry prvního</th>"
                   "<th>n</th></tr>")
        for xy, v in sorted(rep["pairs"].items()):
            out.append(f"<tr><td>{esc(xy[0])} vs {esc(xy[1])}</td><td>{fmt(v['x_win'])}</td><td>{v['n']}</td></tr>")
        out.append("</table></div>")
        for k, reason in sorted(rep["pair_reasons"].items()):
            out.append(f"<p class='reason'><b>{esc(k)}:</b> {esc(reason)}</p>")

    out.append(f"<h2>Finální aplikace (po {esc(rep.get('final_session', 'S4'))})</h2>")
    for r in rep["reps"]:
        shots = {a: rep["final_shots"].get(f"{a}.r{r}", []) for a in rep["arms"]}
        urls = list(dict.fromkeys(x["url"] for a in rep["arms"] for x in shots[a]))
        out.append(f"<h3>Opakování {r}</h3>")
        for url in urls:
            for kind in ("desktop", "mobile"):
                cells = []
                for a in rep["arms"]:
                    shot = next((x for x in shots[a] if x["url"] == url), {})
                    src = shot.get(kind)
                    rel = os.path.relpath(FLOW / src, vdir).replace("\\", "/") if src else None
                    cap = f"{ARM_NAME[a]} · {url} · {kind}"
                    img = f"<img loading='lazy' src='{esc(rel)}' alt='{esc(cap)}'>" if rel else "<p class='note'>stránka chybí</p>"
                    cells.append(f"<figure><figcaption>{esc(cap)}</figcaption>{img}</figure>")
                out.append("<div class='grid3'>" + "".join(cells) + "</div>")
    out.append("</main></body></html>")
    return "\n".join(out)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--variant", required=True)
    a = p.parse_args(argv)
    vdir = MULTI / a.variant
    rep = build(vdir)
    if not rep["per"]:
        print(f"{vdir}: žádné řádky sezení", file=sys.stderr)
        return 2
    (vdir / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (vdir / "report.html").write_text(render(rep, vdir), encoding="utf-8")
    print(f"{vdir / 'report.html'}\n{vdir / 'report.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
