#!/usr/bin/env python3
"""Plán vs. realita: READ-ONLY měření Opora Canvas (jen HTTP GET + čtení souborů).

Použití:
  python tools/plan-vs-realita/mereni.py --project <id> --workspace <wid> \
      [--checkout <cesta>] [--gh] [--base http://127.0.0.1:8740] --out <soubor.json>
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

CARD_KINDS = ("node", "sector")
NO_AREA = "bez oblasti"
FILE_RELATIONS = ("imports", "imports_from", "calls")
_CENTRE_OFFSET = {"node": (180, 120), "sector": (180, 120), "comment": (120, 80)}
PR_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")


# ---------------------------------------------------------------- I/O (jen čtení)
def http_get(base, path, params=None):
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def load_graphify(checkout):
    if not checkout:
        return None
    p = os.path.join(checkout, "graphify-out", "graph.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- oblasti (kopie backend/canvas/areas.py)
def area_of(node, nodes):
    if node.get("kind") == "area":
        return None
    dx, dy = _CENTRE_OFFSET.get(node.get("kind"), (180, 120))
    cx, cy = node["x"] + dx, node["y"] + dy
    cands = []
    for o in nodes:
        if o.get("kind") != "area" or o["id"] == node["id"]:
            continue
        if o.get("parentId") != node.get("parentId"):
            continue
        size = o.get("size")
        if not size:
            continue
        if o["x"] <= cx <= o["x"] + size["w"] and o["y"] <= cy <= o["y"] + size["h"]:
            cands.append(o)
    if not cands:
        return None
    cands.sort(key=lambda a: a["size"]["w"] * a["size"]["h"])
    return cands[0]


# ---------------------------------------------------------------- jednotky plánu
def norm_path(p):
    return (p or "").replace("\\", "/").strip("/")


def leaf_blocks(blocks):
    """Bloky jsou ploché (parentBlockId) a/nebo vnořené (children). Vrací (listy, všechny)."""
    flat = []

    def walk(bl):
        for b in bl or []:
            flat.append(b)
            walk(b.get("children"))

    walk(blocks)
    ids = {b.get("id") for b in flat}
    parents = {b.get("parentBlockId") for b in flat if b.get("parentBlockId") in ids}
    return [b for b in flat if b.get("id") not in parents and not b.get("children")], flat


def step_done(s):
    return bool(s.get("done")) or s.get("status") in ("done", "met")


def card_claimed(done):
    done = done or {}
    return bool(done.get("confirmed")) or (done.get("by") == "agent" and bool(done.get("at")))


def card_units(st):
    """Vrátí (druh, [jednotky]); jednotka = {id,text,done,dependsOn}."""
    st = st or {}
    steps = st.get("steps") or []
    if steps:
        return "step", [{"id": s.get("id"), "text": s.get("text") or s.get("title") or "", "done": step_done(s),
                         "dependsOn": s.get("dependsOn") or []} for s in steps]
    leaves, _ = leaf_blocks(st.get("blocks") or [])
    if leaves:
        return "block", [{"id": b.get("id"), "text": b.get("title") or "",
                          "done": (b.get("state") or {}).get("status") == "met", "dependsOn": []} for b in leaves]
    return "card", [{"id": None, "text": "", "done": card_claimed(st.get("done")), "dependsOn": []}]


def pct(done, total):
    return None if not total else round(100.0 * done / total, 1)


def real_ref(node):
    """sourceRef s neprázdnou cestou, jinak None (prázdná cesta = fakticky bez odkazu)."""
    r = node.get("sourceRef") or {}
    return r if norm_path(r.get("path")) else None


def covers(path, f):
    path, f = norm_path(path), norm_path(f)
    return f == path or f.startswith(path + "/")


def lacks_acceptance(step):
    a = step.get("acceptance")
    if isinstance(a, str):
        return not a.strip()
    return not a


# ---------------------------------------------------------------- hlavní analýza
def analyse(view, state, checkout=None, graphify=None):
    nodes = view["graph"]["nodes"]
    edges = view["graph"]["edges"]
    sn = (state or {}).get("nodes") or {}
    byid = {n["id"]: n for n in nodes}
    cards = [n for n in nodes if n["kind"] in CARD_KINDS]
    areas = [n for n in nodes if n["kind"] == "area"]
    has_checkout = bool(checkout) and os.path.isdir(checkout)

    def exists(p):
        return bool(checkout) and os.path.exists(os.path.join(checkout or "", norm_path(p)))

    rows = {}
    for c in cards:
        st = sn.get(c["id"]) or {}
        kind, units = card_units(st)
        total = len(units)
        a = area_of(c, nodes)
        ref = real_ref(c)
        tv = sum(1 for u in units if u["done"])
        done = st.get("done") or {}
        kod = None
        if has_checkout:
            kod = total if (ref and ref.get("origin") == "existing" and exists(ref["path"])) else 0
        rows[c["id"]] = {
            "id": c["id"], "name": c.get("name"), "kind": c["kind"], "unitKind": kind, "units": total,
            "tvrdi": tv, "kod": kod, "potvrzeno": total if done.get("confirmed") else 0,
            "area": a["name"] if a else NO_AREA, "areaId": a["id"] if a else None,
            "unitList": units, "st": st, "ref": ref,
            "done": bool(done.get("confirmed")) or (total > 0 and tv == total),
        }

    def agg(rs):
        t = sum(r["units"] for r in rs)
        tv = sum(r["tvrdi"] for r in rs)
        po = sum(r["potvrzeno"] for r in rs)
        ko = sum(r["kod"] for r in rs) if has_checkout else None
        return {"cards": len(rs), "units": t, "tvrdi": tv, "kod": ko, "potvrzeno": po,
                "tvrdiPct": pct(tv, t), "kodPct": None if ko is None else pct(ko, t), "potvrzenoPct": pct(po, t)}

    per_area = {}
    for name in sorted({r["area"] for r in rows.values()}):
        per_area[name] = agg([r for r in rows.values() if r["area"] == name])
    for a in areas:
        per_area.setdefault(a["name"], agg([]))
    project = agg(list(rows.values()))

    nxt_in, nxt_out = defaultdict(list), defaultdict(list)
    for e in edges:
        if (e.get("port") or "next") == "next":
            nxt_in[e["target"]].append(e["source"])
            nxt_out[e["source"]].append(e["target"])

    F = []

    def add(type_, r, reason, **ev):
        d = {"type": type_, "reason": reason}
        if r is not None:
            d.update({"cardId": r["id"], "name": r["name"], "area": r["area"]})
        d.update(ev)
        F.append(d)

    def bad_blocks(cid):
        _, flat = leaf_blocks(((sn.get(cid) or {}).get("blocks")) or [])
        return [b for b in flat if (b.get("state") or {}).get("status") in ("unmet", "blocked")]

    for r in rows.values():
        st = r["st"]
        open_units = [u for u in r["unitList"] if not u["done"]]
        if open_units and not r["done"]:
            add("ZBYVA", r, f"{len(open_units)} z {r['units']} jednotek otevřeno", open=len(open_units), units=r["units"],
                openTexts=[u["text"] for u in open_units][:5])
            srcs = nxt_in.get(r["id"], [])
            if srcs and all(s in rows and rows[s]["done"] for s in srcs):
                add("ZBYVA", r, "dalsi_krok: všichni předchůdci (next) jsou hotoví", dalsi_krok=True, predecessors=srcs)
            if r["unitKind"] == "step":
                done_ids = {u["id"] for u in r["unitList"] if u["done"]}
                for u in open_units:
                    if u["dependsOn"] and all(d in done_ids for d in u["dependsOn"]):
                        add("ZBYVA", r, "dalsi_krok: krok má splněné dependsOn", dalsi_krok=True,
                            stepId=u["id"], text=u["text"])
        _, flat = leaf_blocks(st.get("blocks") or [])
        for b in flat:
            bs = b.get("state") or {}
            if bs.get("status") in ("unmet", "blocked") and (bs.get("onUnmet") or {}).get("kind", "none") == "none":
                add("SLEPA_ULICKA", r, f"blok {bs['status']} bez onUnmet", blockId=b.get("id"), blockTitle=b.get("title"))
            for p in b.get("ports") or []:
                if not any(e.get("port") == "block" and e.get("sourceBlockId") == b.get("id")
                           and e.get("sourcePortId") == p.get("id") for e in edges):
                    add("SLEPA_ULICKA", r, "port bloku bez hrany", blockId=b.get("id"), portId=p.get("id"),
                        portLabel=p.get("label"))
        if not r["done"]:
            if not nxt_in.get(r["id"]) and not nxt_out.get(r["id"]):
                add("SLEPA_ULICKA", r, "nedokončená karta bez next hran (izolovaná)")
            for s in nxt_in.get(r["id"], []):
                if s in rows and bad_blocks(s):
                    add("SLEPA_ULICKA", r, "předchůdce má unmet/blocked blok", predecessor=rows[s]["name"],
                        predecessorId=s)
        if not r["ref"]:
            add("DOPLNIT", r, "karta bez sourceRef")
        if not (st.get("steps") or st.get("blocks") or st.get("criteria")):
            add("DOPLNIT", r, "karta bez kroků, bloků i kritérií")
        for s in st.get("steps") or []:
            if lacks_acceptance(s):
                add("DOPLNIT", r, "krok bez acceptance", stepId=s.get("id"), text=s.get("text"))
        ref = r["ref"]
        if ref and has_checkout:
            ex = exists(ref["path"])
            if ref.get("origin") == "planned" and ex:
                add("VYMENIT", r, "plánovaná cesta už existuje: planned -> existing", path=ref["path"],
                    propose="existing")
            elif ref.get("origin") == "existing" and not ex:
                add("VYMENIT", r, "existující cesta chybí (přesunuto/smazáno): nahradit", path=ref["path"],
                    propose="replace")
    for a in areas:
        if per_area[a["name"]]["cards"] == 0:
            F.append({"type": "DOPLNIT", "reason": "oblast bez karet", "cardId": a["id"], "name": a["name"],
                      "area": a["name"]})

    by_path = defaultdict(list)
    for r in rows.values():
        if r["ref"] and r["ref"].get("origin") == "existing":
            by_path[norm_path(r["ref"]["path"])].append(r)
    for p, rs in by_path.items():
        if len(rs) > 1:
            F.append({"type": "UBRAT", "reason": "více karet na stejné existující cestě", "path": p, "name": p,
                      "cards": [{"id": x["id"], "name": x["name"], "area": x["area"]} for x in rs],
                      "area": ", ".join(sorted({x["area"] for x in rs}))})

    coverage = None
    if graphify is not None:
        nid2file = {n["id"]: norm_path(n.get("source_file")) for n in graphify["nodes"] if n.get("source_file")}
        files = sorted(set(nid2file.values()))
        fe = Counter()
        for l in graphify.get("links") or graphify.get("edges") or []:
            if l.get("relation") not in FILE_RELATIONS:
                continue
            a, b = nid2file.get(l.get("source")), nid2file.get(l.get("target"))
            if a and b and a != b:
                fe[(a, b)] += 1
        ex_refs = [(norm_path(r["ref"]["path"]), r) for r in rows.values()
                   if r["ref"] and r["ref"].get("origin") == "existing"]

        def owner(f):
            best = None
            for p, r in ex_refs:
                if covers(p, f) and (best is None or len(p) > best[0]):
                    best = (len(p), r)
            return best[1] if best else None

        owners = {f: owner(f) for f in files}
        covered = [f for f in files if owners[f]]
        coverage = {"files": len(files), "covered": len(covered), "pct": pct(len(covered), len(files))}

        def area_id_of(nid):
            n = byid.get(nid)
            if not n:
                return None
            return n["id"] if n["kind"] == "area" else (rows[nid]["areaId"] if nid in rows else None)

        flow_pairs, any_pairs = set(), set()
        for e in edges:
            any_pairs.add(frozenset((e["source"], e["target"])))
            sa, ta = area_id_of(e["source"]), area_id_of(e["target"])
            if e.get("port") == "flow" and sa and ta:
                flow_pairs.add(frozenset((sa, ta)))
        nc = {}
        for (a, b), cnt in fe.items():
            oa, ob = owners[a], owners[b]
            if not oa or not ob or not oa["areaId"] or not ob["areaId"] or oa["areaId"] == ob["areaId"]:
                continue
            if frozenset((oa["areaId"], ob["areaId"])) in flow_pairs or frozenset((oa["id"], ob["id"])) in any_pairs:
                continue
            d = nc.setdefault((oa["area"], ob["area"]), {"count": 0, "samples": []})
            d["count"] += cnt
            if len(d["samples"]) < 5:
                d["samples"].append([a, b])
        for (a, b), d in sorted(nc.items(), key=lambda kv: -kv[1]["count"]):
            F.append({"type": "NOVA_CESTA", "reason": "souborové závislosti mezi oblastmi bez flow/hrany",
                      "name": f"{a} -> {b}", "area": a, "toArea": b, "count": d["count"], "samples": d["samples"]})

        nbr, tot = defaultdict(Counter), Counter()
        for (a, b), cnt in fe.items():
            for x, y in ((a, b), (b, a)):
                tot[x] += cnt
                held = owners.get(y)
                if held:
                    nbr[x][held["area"]] += cnt
        for f in files:
            if owners.get(f):
                continue
            sug = nbr[f].most_common(1)
            F.append({"type": "SIROTEK", "reason": "soubor nekryje žádný existing sourceRef", "name": f,
                      "area": None, "file": f, "suggestArea": sug[0][0] if sug else None,
                      "suggestScore": f"{sug[0][1]}/{tot[f]}" if sug else None})

    out_rows = [{k: v for k, v in r.items() if k not in ("unitList", "st", "ref")} for r in rows.values()]
    return {"project": project, "areas": per_area, "cards": out_rows, "coverage": coverage,
            "findings": F, "counts": dict(Counter(f["type"] for f in F)),
            "checkout": checkout if has_checkout else None}


def collect_pr_urls(state):
    urls = set()
    for n in ((state or {}).get("nodes") or {}).values():
        urls.update(PR_RE.findall(json.dumps(n, ensure_ascii=False)))
    return sorted(urls)


def gh_pr_states(urls):
    """Jen čtení: `gh pr view <url> --json state,mergedAt`."""
    out = {}
    for u in urls:
        try:
            p = subprocess.run(["gh", "pr", "view", u, "--json", "state,mergedAt"], capture_output=True, text=True,
                               timeout=30, encoding="utf-8")
            out[u] = json.loads(p.stdout) if p.returncode == 0 else {"error": p.stderr.strip()[:200]}
        except Exception as ex:  # noqa: BLE001
            out[u] = {"error": str(ex)}
    return out


# ---------------------------------------------------------------- Markdown
def fmt(v):
    return "n/a" if v is None else f"{v}%"


def markdown(res, title=""):
    p = res["project"]
    cov = res["coverage"]
    L = [f"# Plán vs. realita {title}".strip(), "",
         f"Projekt: {p['cards']} karet, {p['units']} jednotek; tvrdí {fmt(p['tvrdiPct'])}, kód {fmt(p['kodPct'])}, "
         f"potvrzeno {fmt(p['potvrzenoPct'])}. Pokrytí graphify: "
         + (f"{cov['pct']}% ({cov['covered']}/{cov['files']})" if cov else "n/a"),
         "", "| Oblast | Karty | Jednotky | tvrdí | kód | potvrzeno |", "|---|---|---|---|---|---|"]
    for n, a in res["areas"].items():
        L.append(f"| {n} | {a['cards']} | {a['units']} | {fmt(a['tvrdiPct'])} | {fmt(a['kodPct'])} | "
                 f"{fmt(a['potvrzenoPct'])} |")
    L += ["", "## Nálezy", ""]
    for t in ("ZBYVA", "SLEPA_ULICKA", "NOVA_CESTA", "SIROTEK", "DOPLNIT", "UBRAT", "VYMENIT"):
        items = [f for f in res["findings"] if f["type"] == t]
        L.append(f"- **{t}**: {len(items)}")
        for f in items[:3]:
            L.append(f"  - {f.get('name')} ({f.get('area')}): {f['reason']}")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Plán vs. realita (read-only)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--workspace", default="draft")
    ap.add_argument("--checkout")
    ap.add_argument("--base", default="http://127.0.0.1:8740")
    ap.add_argument("--gh", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    q = {"project": a.project, "workspace": a.workspace}
    boot = http_get(a.base, "/api/bootstrap")
    proj = next((p for p in boot.get("projects", []) if p["id"] == a.project), {})
    checkout = a.checkout or (proj.get("sourcePath") if proj.get("sourceKind") in ("git", "local") else None)
    view = http_get(a.base, "/api/view", q)
    state = http_get(a.base, "/api/desktop-v3/state", q).get("state")
    gr = load_graphify(checkout) if checkout and os.path.isdir(checkout) else None
    res = analyse(view, state, checkout, gr)
    if a.gh:
        res["gh"] = gh_pr_states(collect_pr_urls(state))
    res["meta"] = {"project": a.project, "projectName": proj.get("name"), "workspace": a.workspace}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    print(markdown(res, f"- {proj.get('name', a.project)}"))


if __name__ == "__main__":
    main()
