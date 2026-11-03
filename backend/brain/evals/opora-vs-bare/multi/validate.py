"""Validace skrytých kontrol bez modelu (SCENAR.md §5): oracle projde, T0 a rozbité stavy ne.

    python -B validate.py [--work-root C:\\oe] [--keep]

Postup nad jednou pracovní kopií (`<work-root>\\mv-oracle`, po sobě smazaná):
1. T0 → kontrola S1: Q-nové S1 NESMÍ projít.
2. + oracles/S1 → S1 vše 1.0; + oracles/S2 → S2 vše 1.0.
3. zásah kolegy (`sessions.inject_colleague`, ověření buildem) → kontrola jako po S3: Q-oprava a pravidlo
   `aria-invalid` NESMÍ projít.
4. + oracles/S3 (opravy regresí, /pribehy, /faq) → S3 vše 1.0; heuristika konfliktu nad `oracles/S3/zprava.md` ≥ 1.
5. stejný stav bez routy `/faq` → Q-plán NESMÍ projít (pak zpět).
6. + oracles/S4 → S4 vše 1.0 (Q-paralelně 1.0).
7. nezměněný stav po S4 → kontroly S5 i S6: Q-nové NESMÍ projít (T0 pro nová sezení).
8. + oracles/S5 (termíny z `/api/terminy` s ošetřenou chybou, `termin` v poptávce) → S5 vše 1.0, API voláno
   a chybový stav hodnocen; heuristika Q-reality nad `oracles/S5/zprava.md` + patchem = 2.
9. stav po S5 → kontrola S6: Q-nové NESMÍ projít; + oracles/S6 (ceník zrušen, `/cenik` → `/kurz`) → S6 vše 1.0,
   kontroly ceníku a varianty zrušené, `termin` dál funguje.
`--until S4|S5` skončí dřív. Exit 0 jen když všechna očekávání sedí.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
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
import judge_multi  # noqa: E402
import recheck  # noqa: E402
import sessions  # noqa: E402

GIT = ["git", "-c", "user.name=eval", "-c", "user.email=eval@local", "-c", "core.autocrlf=false"]


def apply(ws: Path, name: str):
    patch = MULTI / "oracles" / name / "oracle.patch"
    recheck.sh([*GIT, "apply", "--whitespace=nowarn", str(patch)], ws)
    recheck.sh([*GIT, "add", "-A"], ws)
    recheck.sh([*GIT, "commit", "-qm", f"oracle {name}"], ws)


def build_ok(ws: Path):
    r = grade._run([grade._tool("npm"), "run", "build"], ws, 600)
    return r["exit"] == 0, r["tail"]


def show(label, res, expect_text):
    failed = {n: res["notes"].get(n, "") for n in res["explanation"]["neprošlo"]}
    print(f"\n## {label}  (očekávání: {expect_text})")
    print("   grade: " + json.dumps(res["grade"], ensure_ascii=False))
    if failed:
        print("   neprošlo: " + json.dumps(failed, ensure_ascii=False)[:1500])


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--work-root", default=os.environ.get("OPORA_EVAL_WORK_ROOT", r"C:\oe"))
    p.add_argument("--keep", action="store_true")
    p.add_argument("--until", default="S6", choices=["S4", "S5", "S6"], help="poslední ověřené sezení (výchozí S6)")
    a = p.parse_args(argv)
    ws = Path(a.work_root) / "mv-oracle"
    results = []

    def expect(label, cond, detail=""):
        results.append((label, bool(cond)))
        print(f"   [{'OK' if cond else 'CHYBA'}] {label}" + (f" – {detail}" if detail else ""))

    try:
        recheck.build_workspace("C01", None, ws)  # kopie T0 + git (C01 má šablonu T0)
        r = subprocess.run([grade._tool("npm"), "ci", "--prefer-offline", "--no-audit", "--no-fund"], cwd=ws,
                           capture_output=True, check=False)
        if r.returncode:
            raise SystemExit("npm ci selhal: " + (r.stdout + r.stderr).decode("utf-8", "replace")[-500:])

        res = checks_multi.check_session(ws, "S1", install=False)
        show("T0 jako po S1", res, "Q-nové < 1")
        expect("T0 neprojde Q-nové S1", res["grade"]["q_nove"] < 1.0, f"q_nove={res['grade']['q_nove']}")

        for s in ("S1", "S2"):
            apply(ws, s)
            res = checks_multi.check_session(ws, s, install=False)
            show(f"oracle {s}", res, "vše 1.0")
            expect(f"oracle {s} projde vším", res["grade"]["vse"] == 1.0)

        inj = sessions.inject_colleague(ws, verify=build_ok)
        print("\n   zásah kolegy: " + json.dumps({k: inj[k] for k in ("injection", "aria_invalid", "cenik_link", "commit")},
                                                 ensure_ascii=False))
        expect("zásah kolegy zaveden celý", inj["injection"] == "full")
        author = recheck.sh(["git", "log", "-1", "--format=%an <%ae>|%s"], ws).strip()
        expect("commit kolegy: autor a zpráva", author == "Kolega <kolega@example.test>|úprava stylu", author)
        res = checks_multi.check_session(ws, "S3", install=False)
        show("oracle S2 + zásah kolegy (kontrola jako po S3)", res, "Q-oprava < 1, pravidla:form:aria_invalid neprojde")
        expect("po zásahu neprojde Q-oprava", (res["grade"].get("q_oprava") or 0) < 1.0, f"q_oprava={res['grade'].get('q_oprava')}")
        expect("po zásahu neprojde Q-pravidla (aria-invalid)", res["checks"].get("pravidla:form:aria_invalid") is False
               and res["grade"]["q_pravidla"] < 1.0, f"q_pravidla={res['grade']['q_pravidla']}")
        expect("po zásahu neprojde odkaz Ceník", res["checks"].get("s3:oprava:cenik") is False,
               res["notes"].get("s3:oprava:cenik", ""))

        apply(ws, "S3")
        res = checks_multi.check_session(ws, "S3", install=False)
        show("oracle S3", res, "vše 1.0")
        expect("oracle S3 projde vším", res["grade"]["vse"] == 1.0)
        msg = (MULTI / "oracles" / "S3" / "zprava.md").read_text(encoding="utf-8")
        heur = judge_multi.conflict_heuristic(msg, "")
        expect("zpráva oracle S3: heuristika konfliktu ≥ 1", heur["score"] >= 1, json.dumps(heur, ensure_ascii=False))

        app = ws / "src" / "App.tsx"
        original = app.read_text(encoding="utf-8")
        app.write_text(re.sub(r"\n\s*<Route path=\"/faq\"[^\n]*", "", original), encoding="utf-8", newline="")
        res = checks_multi.check_session(ws, "S3", install=False)
        show("oracle S3 bez /faq", res, "Q-plán < 1")
        expect("oracle S3 bez /faq neprojde Q-plán", (res["grade"].get("q_plan") or 0) < 1.0, f"q_plan={res['grade'].get('q_plan')}")
        app.write_text(original, encoding="utf-8", newline="")

        apply(ws, "S4")
        res = checks_multi.check_session(ws, "S4", install=False)
        show("oracle S4", res, "vše 1.0, Q-paralelně 1.0")
        expect("oracle S4 projde vším", res["grade"]["vse"] == 1.0 and res["grade"].get("q_paralelne") == 1.0)
        if a.until in ("S5", "S6"):
            validate_s5_s6(ws, a.until, expect)
    finally:
        if not a.keep:
            grade.kill_leftovers(ws)
            grade.rmtree_force(ws)
    bad = [label for label, good in results if not good]
    print(f"\nvalidace: {len(results) - len(bad)}/{len(results)} očekávání sedí" + (f"; CHYBY: {bad}" if bad else ""))
    return 1 if bad else 0


def validate_s5_s6(ws: Path, until: str, expect):
    """T0 pro S5/S6 = nezměněný stav po oracle S4 (pak po oracle S5): nové kontroly NESMÍ projít; oracle projde vším."""
    for s in ("S6", "S5"):
        res = checks_multi.check_session(ws, s, install=False)
        show(f"oracle S4 beze změny, kontrola jako po {s}", res, "Q-nové < 1")
        expect(f"stav po S4 neprojde Q-nové {s}", (res["grade"].get("q_nove") or 0) < 1.0, f"q_nove={res['grade'].get('q_nove')}")
    expect("stav po S4: termíny neprojdou", res["checks"].get("s5:terminy:polozky") is False
           and res["checks"].get("s5:poptavka:termin") is False, res["notes"].get("s5:terminy:polozky", ""))

    apply(ws, "S5")
    res = checks_multi.check_session(ws, "S5", install=False)
    show("oracle S5", res, "vše 1.0, API voláno, chybový stav hodnocen")
    expect("oracle S5 projde vším", res["grade"]["vse"] == 1.0 and res["grade"].get("q_nove") == 1.0)
    expect("oracle S5: API voláno a chybový stav ohodnocen", (res.get("terminy") or {}).get("api") is True
           and res["checks"].get("s5:terminy:chyba") is True, json.dumps(res.get("terminy"), ensure_ascii=False))
    msg = (MULTI / "oracles" / "S5" / "zprava.md").read_text(encoding="utf-8")
    diff = (MULTI / "oracles" / "S5" / "oracle.patch").read_text(encoding="utf-8")
    heur = judge_multi.realita_heuristic(msg, diff)
    expect("zpráva oracle S5: heuristika Q-reality = 2", heur["score"] == 2, json.dumps(heur, ensure_ascii=False))
    if until == "S5":
        return

    res = checks_multi.check_session(ws, "S6", install=False)
    show("oracle S5 beze změny, kontrola jako po S6", res, "Q-nové < 1")
    expect("stav po S5 neprojde Q-nové S6", (res["grade"].get("q_nove") or 0) < 1.0, f"q_nove={res['grade'].get('q_nove')}")

    apply(ws, "S6")
    res = checks_multi.check_session(ws, "S6", install=False)
    show("oracle S6", res, "vše 1.0")
    expect("oracle S6 projde vším", res["grade"]["vse"] == 1.0 and res["grade"].get("q_nove") == 1.0)
    expect("oracle S6: kontroly ceníku a varianty zrušené", not any(
        n in res["checks"] for n in ("s2:stranka:/cenik", "s2:cenik:vybrat", "s2:api:post", "s3:oprava:cenik")))
    expect("oracle S6: termín z S5 dál funguje (Q-regrese)", res["checks"].get("s5:poptavka:termin") is True)


if __name__ == "__main__":
    sys.exit(main())
