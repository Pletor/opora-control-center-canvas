"""Zpráva evalu „OPORA vs. bez OPORY“ podle metriky.md §4: `<varianta>/report.html` + `<varianta>/report.json`.

    python -B report.py --variant baseline
    python -B report.py --variant v2

Čte jen `<varianta>/results.jsonl` (řádky A, B a soudce `pair`; u soudce platí nejnovější řádek `judge_v 2`).
Kvalita řádku = průměr dostupných Q1–Q4 (0–1) a Q5–Q7 převedených na 0–1 ((s − 1) / 4); zisk OPORY =
kvalita A − kvalita B na stejném případu, průměr přes opakování; kvalita na minutu agenta a na USD (cena hlášená
CLI). Tabulka „lepší / horší / stejné“: rozdíl < 0,05 (podíly), < 0,5 bodu (škála 1–5), < 5 % (cena práce).
Samostatná stránka bez externích knihoven; screenshoty relativní cestou (`shots/…`).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path

FLOW = Path(__file__).resolve().parent

# (klíč, popisek, druh) – druh: share (0–1, vyšší lepší), score (1–5), cost (nižší lepší), win (pair_win A)
METRICS = [
    ("q1", "Q1 Funkčnost", "share"), ("q2", "Q2 Pokrytí záměru", "share"), ("q3", "Q3 Stavy", "share"),
    ("q4", "Q4 Přístupnost", "share"), ("q5", "Q5 Vzhled a pocit", "score"), ("q6", "Q6 Věrnost textu", "score"),
    ("q7", "Q7 Kvalita kódu", "score"), ("q8", "Q8 Testy (termíny záměru)", "share"), ("q9", "Q9 Verdikt soudce (výhra A)", "win"),
    ("checks_pass", "Všechny kontroly prošly", "share"), ("quality", "Kvalita (§4)", "share"),
    ("c1", "C1 Čas agenta [min]", "cost"), ("c2_cost", "C2 Cena [USD]", "cost"), ("c2_out", "C2 Výstupní tokeny", "cost"),
    ("c2_in", "C2 Vstupní tokeny vč. cache", "cost"), ("c3_calls", "C3 Volání nástrojů", "cost"), ("c3_turns", "C3 Tahy", "cost"),
    ("c4", "C4 Zbytečné pokusy", "cost"), ("c5", "C5 Soubory mimo zadání", "cost"),
    ("q_per_min", "Kvalita / minuta", "share"), ("q_per_usd", "Kvalita / USD", "share"),
]
LABEL = {k: lab for k, lab, _ in METRICS}
KIND = {k: kind for k, _, kind in METRICS}


def rows_of(vdir: Path):
    path = vdir / "results.jsonl"
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()] if path.exists() else []
    arms, pairs = {}, {}
    for r in rows:
        meta = r.get("meta", {})
        if r.get("status") != "ok":
            continue
        if meta.get("arm") in ("A", "B"):
            arms[(meta["case"], meta["arm"], r["rep"])] = r
        elif meta.get("arm") == "pair":
            key = (meta["case"], r["rep"])
            if meta.get("judge_v", 1) >= (pairs.get(key, {}).get("meta", {}).get("judge_v", 0)):
                pairs[key] = r
    return arms, pairs


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def arm_metrics(row, pair, arm):
    g, cost, usage = row.get("grade", {}), row.get("cost", {}), row.get("usage") or {}
    pg = (pair or {}).get("grade", {}) if (pair or {}).get("meta", {}).get("judge_v") == 2 else {}
    m = {"q1": g.get("q1_funkcnost"), "q2": g.get("q2_pokryti"), "q3": g.get("q3_stavy"), "q4": g.get("q4_pristupnost"),
         "q5": pg.get(f"q5_vzhled_{arm}"), "q6": pg.get(f"q6_vernost_{arm}"), "q7": pg.get(f"q7_kod_{arm}"),
         "q8": g.get("q8_testy"), "checks_pass": g.get("checks_pass"),
         "q9": (pair or {}).get("grade", {}).get("pair_win") if pair else None,
         "c1": round(row.get("latency_s", 0) / 60, 2), "c2_cost": row.get("meta", {}).get("reported_cost_usd"),
         "c2_out": usage.get("output_tokens"),
         "c2_in": sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) or None,
         "c3_calls": row.get("tool_calls"), "c3_turns": row.get("turns"),
         "c4": cost.get("c4_zbytecne"), "c5": cost.get("c5_mimo_zadani"),
         "tests_passed": row.get("meta", {}).get("tests", {}).get("tests_passed")}
    if arm == "B" and m["q9"] is not None:
        m["q9"] = 1 - m["q9"]
    parts = [m[k] for k in ("q1", "q2", "q3", "q4")] + [(m[k] - 1) / 4 if m[k] is not None else None for k in ("q5", "q6", "q7")]
    m["quality"] = round(_mean(parts), 4) if _mean(parts) is not None else None
    m["q_per_min"] = round(m["quality"] / m["c1"], 4) if m["quality"] is not None and m["c1"] else None
    m["q_per_usd"] = round(m["quality"] / m["c2_cost"], 4) if m["quality"] is not None and m["c2_cost"] else None
    return m


def verdict(key, a, b):
    """'A lepší' / 'A horší' / 'stejné' / None podle prahů metriky.md §4."""
    if a is None or b is None:
        return None
    kind, d = KIND[key], a - b
    if kind == "cost":
        base = max(abs(a), abs(b))
        if not base or abs(d) / base < 0.05:
            return "stejné"
        return "A lepší" if d < 0 else "A horší"
    thr = 0.5 if kind == "score" else 0.05
    if abs(d) < thr:
        return "stejné"
    return "A lepší" if d > 0 else "A horší"


def build(vdir: Path):
    arms, pairs = rows_of(vdir)
    cases = sorted({c for c, _a, _r in arms})
    per_case, per_rep, opora = {}, [], []
    for case in cases:
        reps = sorted({r for c, _a, r in arms if c == case})
        acc = {"A": [], "B": []}
        for rep in reps:
            pair = pairs.get((case, rep))
            rec = {"case": case, "rep": rep, "pair": bool(pair), "judge_reason": (pair or {}).get("meta", {}).get("verdict", {}).get("reason"),
                   "judge_v": (pair or {}).get("meta", {}).get("judge_v")}
            for arm in "AB":
                row = arms.get((case, arm, rep))
                if row is None:
                    continue
                m = arm_metrics(row, pair, arm)
                acc[arm].append(m)
                rec[arm] = m
                rec[f"shots_{arm}"] = row.get("meta", {}).get("shots") or []
                if arm == "A":
                    opora.append({"case": case, "rep": rep, **(row.get("opora") or {}),
                                  "c4_chyby_opora": (row.get("cost") or {}).get("c4_chyby_opora")})
            per_rep.append(rec)
        means = {arm: {k: _mean([m.get(k) for m in acc[arm]]) for k in LABEL} for arm in "AB" if acc[arm]}
        if "A" in means and "B" in means:
            means["gain"] = (means["A"]["quality"] - means["B"]["quality"]) if means["A"]["quality"] is not None \
                and means["B"]["quality"] is not None else None
        means["reps"] = len(reps)
        per_case[case] = means
    summary = {}
    both = [rec for rec in per_rep if "A" in rec and "B" in rec]
    for key in LABEL:
        a = _mean([rec["A"].get(key) for rec in both])
        b = _mean([rec["B"].get(key) for rec in both])
        if key == "q9":
            summary[key] = {"A": a, "B": b, "verdict": None if a is None else
                            ("stejné" if abs(a - 0.5) < 0.05 else "A lepší" if a > 0.5 else "A horší")}
        else:
            summary[key] = {"A": a, "B": b, "verdict": verdict(key, a, b)}
    gains = [per_case[c].get("gain") for c in cases if per_case[c].get("gain") is not None]
    return {"variant": vdir.name, "cases": cases, "pairs": len(both), "per_case": per_case, "per_rep": per_rep,
            "summary": summary, "gain_mean": _mean(gains), "opora": opora}


# --- HTML -----------------------------------------------------------------------------------------

CSS = """
:root{--bg:#f7f6f2;--panel:#fff;--ink:#1d1f1c;--muted:#5d625a;--line:#dedbd2;--good:#1f7a45;--bad:#b23a2a;--same:#6b6f68;--accent:#2f5d8a}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151714;--panel:#1e211d;--ink:#e8e9e4;--muted:#a3a89f;--line:#33372f;--good:#5cc489;--bad:#ef7d6b;--same:#9da296;--accent:#8db7e0}}
:root[data-theme="dark"]{--bg:#151714;--panel:#1e211d;--ink:#e8e9e4;--muted:#a3a89f;--line:#33372f;--good:#5cc489;--bad:#ef7d6b;--same:#9da296;--accent:#8db7e0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 10px}
h3{font-size:16px;margin:22px 0 8px}.lead{color:var(--muted);margin:0 0 18px}.note{color:var(--muted);font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.card span{color:var(--muted);font-size:13px}
.wrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{font-size:13px;color:var(--muted);font-weight:600}tr:last-child td{border-bottom:0}
.v-good{color:var(--good);font-weight:600}.v-bad{color:var(--bad);font-weight:600}.v-same{color:var(--same)}
.shots{display:grid;grid-template-columns:1fr 1fr;gap:12px}.shots figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px}
.shots figcaption{font-size:13px;color:var(--muted);margin-bottom:6px}.shots img{width:100%;height:auto;max-height:640px;object-fit:cover;object-position:top;border-radius:6px;display:block}
.shots .m img{max-width:220px;margin:0 auto}.reason{background:var(--panel);border-left:3px solid var(--accent);padding:8px 12px;border-radius:4px;color:var(--ink);font-size:14px}
@media (max-width:640px){.shots{grid-template-columns:1fr}}
"""


def fmt(v, key=None):
    if v is None:
        return "–"
    if isinstance(v, float):
        if key in ("c2_cost",):
            return f"{v:.2f}"
        return f"{v:.2f}" if abs(v) < 1000 else f"{v:,.0f}".replace(",", " ")
    if isinstance(v, int) and abs(v) >= 1000:
        return f"{v:,}".replace(",", " ")
    return str(v)


def vclass(v):
    return {"A lepší": "v-good", "A horší": "v-bad", "stejné": "v-same"}.get(v, "")


def esc(x):
    return html.escape(str(x))


def render(rep, vdir: Path):
    s = rep["summary"]
    out = [f"<!doctype html><html lang='cs'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>OPORA vs. bez OPORY</title><style>{CSS}</style></head><body><main>",
           "<h1>OPORA vs. bez OPORY</h1>",
           f"<p class='lead'>Varianta <b>{esc(rep['variant'])}</b> · případy {esc(', '.join(rep['cases']))} · "
           f"{rep['pairs']} dvojic A/B. Rameno A = skill + izolovaná OPORA, B = stejné zadání bez ní. "
           "Při 1–2 opakováních na rameno a případ jsou výsledky orientační, ne statisticky průkazné.</p>"]
    qa, qb = s["quality"]["A"], s["quality"]["B"]
    cards = [("Kvalita A", fmt(qa)), ("Kvalita B", fmt(qb)), ("Zisk OPORY (A − B)", fmt(rep["gain_mean"])),
             ("Kvalita / min A · B", f"{fmt(s['q_per_min']['A'])} · {fmt(s['q_per_min']['B'])}"),
             ("Kvalita / USD A · B", f"{fmt(s['q_per_usd']['A'])} · {fmt(s['q_per_usd']['B'])}"),
             ("Čas agenta A · B [min]", f"{fmt(s['c1']['A'])} · {fmt(s['c1']['B'])}")]
    out.append("<div class='cards'>" + "".join(f"<div class='card'><span>{esc(k)}</span><b>{esc(v)}</b></div>" for k, v in cards) + "</div>")
    out.append("<h2>V čem je A lepší, horší, stejné</h2><p class='note'>Průměr přes dvojice A/B. Stejné = rozdíl &lt; 0,05 "
               "(podíly 0–1), &lt; 0,5 bodu (škála 1–5), &lt; 5 % (cena práce, nižší je lepší). Q9 = podíl výher A u soudce "
               "(remíza 0,5).</p><div class='wrap'><table><tr><th>Metrika</th><th>A</th><th>B</th><th>Rozdíl A − B</th><th>Výsledek</th></tr>")
    for key, lab, _k in METRICS:
        a, b, v = s[key]["A"], s[key]["B"], s[key]["verdict"]
        d = None if a is None or b is None or key == "q9" else a - b
        out.append(f"<tr><td>{esc(lab)}</td><td>{fmt(a, key)}</td><td>{fmt(b, key) if key != 'q9' else '–'}</td>"
                   f"<td>{fmt(d, key)}</td><td class='{vclass(v)}'>{esc(v or '–')}</td></tr>")
    out.append("</table></div>")

    out.append("<h2>Po případech</h2><p class='note'>Průměr přes opakování. Δ = A − B.</p><div class='wrap'><table><tr><th>Metrika</th>")
    for c in rep["cases"]:
        out.append(f"<th>{esc(c)} A</th><th>{esc(c)} B</th><th>Δ</th>")
    out.append("</tr>")
    for key, lab, _k in METRICS:
        out.append(f"<tr><td>{esc(lab)}</td>")
        for c in rep["cases"]:
            pc = rep["per_case"][c]
            a, b = pc.get("A", {}).get(key), pc.get("B", {}).get(key)
            v = verdict(key, a, b) if key != "q9" else None
            out.append(f"<td>{fmt(a, key)}</td><td>{fmt(b, key) if key != 'q9' else '–'}</td>"
                       f"<td class='{vclass(v)}'>{fmt(None if a is None or b is None or key == 'q9' else a - b, key)}</td>")
        out.append("</tr>")
    out.append("</table></div>")

    out.append("<h2>Práce s OPOROU (jen A)</h2><p class='note'>P1–P3 ze snímku izolované OPORY po běhu (pilot před v2 "
               "snímek nemá); P4 z volání nástrojů a jejich času, P5 = poznámky .md/.txt v repu.</p>"
               "<div class='wrap'><table><tr><th>Běh</th><th>Stránky (s goal/feel/sections)</th><th>Cesty</th><th>Karty / s kroky / kroků</th>"
               "<th>Karty hotové</th><th>Díry mapy</th><th>Cesty ověřené</th><th>Sekce mapy v kódu</th><th>Podíl volání OPORA</th>"
               "<th>Podíl času OPORA</th><th>Chyby OPORY</th><th>Poznámky v repu</th></tr>")
    for o in rep["opora"]:
        snap = o.get("snapshot")
        pv = lambda k: fmt(o.get(k)) if snap else "–"  # noqa: E731
        out.append(f"<tr><td>{esc(o['case'])} r{o['rep']}</td><td>{pv('p1_pages')} ({pv('p1_pages_full')})</td><td>{pv('p1_journeys')}</td>"
                   f"<td>{pv('p1_cards')} / {pv('p1_cards_with_steps')} / {pv('p1_steps')}</td><td>{pv('p2_cards_done')}</td>"
                   f"<td>{pv('p2_map_gaps')}</td><td>{pv('p2_journeys_verified')}</td><td>{pv('p3_map_in_code')}/{pv('p3_map_sections')}</td>"
                   f"<td>{fmt(o.get('p4_podil_volani'))}</td><td>{fmt(o.get('p4_podil_casu'))}</td><td>{fmt(o.get('c4_chyby_opora'))}</td>"
                   f"<td>{fmt(o.get('p5_poznamky_v_repu'))}</td></tr>")
    out.append("</table></div>")

    out.append("<h2>Výstupy vedle sebe</h2>")
    for rec in rep["per_rep"]:
        out.append(f"<h3>{esc(rec['case'])} · opakování {rec['rep']}</h3>")
        if rec.get("judge_reason"):
            out.append(f"<p class='reason'><b>Soudce (v{rec.get('judge_v')}):</b> {esc(rec['judge_reason'])}</p>")
        sa, sb = rec.get("shots_A", []), rec.get("shots_B", [])
        urls = list(dict.fromkeys([x["url"] for x in sa] + [x["url"] for x in sb]))
        for url in urls:
            for kind in ("desktop", "mobile"):
                cells = []
                for arm, shots in (("A", sa), ("B", sb)):
                    shot = next((x for x in shots if x["url"] == url), {})
                    src = shot.get(kind)
                    rel = os.path.relpath(FLOW / src, vdir).replace("\\", "/") if src else None
                    cap = f"{arm} {'s OPOROU' if arm == 'A' else 'bez OPORY'} · {url} · {kind}"
                    img = f"<img loading='lazy' src='{esc(rel)}' alt='{esc(cap)}'>" if rel else "<p class='note'>screenshot chybí</p>"
                    cells.append(f"<figure class='{'m' if kind == 'mobile' else ''}'><figcaption>{esc(cap)}</figcaption>{img}</figure>")
                out.append("<div class='shots'>" + "".join(cells) + "</div>")
    out.append("</main></body></html>")
    return "\n".join(out)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--variant", required=True)
    args = p.parse_args(argv)
    vdir = FLOW / args.variant
    rep = build(vdir)
    if not rep["cases"]:
        print(f"{vdir}: žádné řádky A/B", file=sys.stderr)
        return 2
    (vdir / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (vdir / "report.html").write_text(render(rep, vdir), encoding="utf-8")
    print(f"{vdir / 'report.html'}\n{vdir / 'report.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
