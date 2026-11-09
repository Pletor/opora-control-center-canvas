"""Příkaz `research` srdce: výzkumný stůl nad schránkou zadání (docs/brain-heart.md §3c, §3d), jen standardní knihovna.

Dávka srdce (`command.py`) soubor kopíruje do `brain/` vedle `opora_heart.py` (s `research_desk.py`, `research_digest.py`,
`research_fetch.py` a `opora_duel.py`); nástroj sem předá sám sebe (`tool`): volání OPORY s tokenem srdce
(`tool.call`), proces se zabitím celého stromu (`tool._execute`, runner stolu), `Failure`, `scope`, `DILNA`
a zápis do `dilna/runs.jsonl` (`tool.log_run`, odtud dávka sečte `subCostUsd`).

Fragment `research` pod F (jinak pod kořenem „Výzkum srdce“) → `research_desk.run_desk` (jeden výzkumník, ověření
citací kódem, destilace na Sonnetu) → `research-update` s verdiktem, digestem jako `approach` a ≤ 6 ověřenými URL. Celý
výsledek s fakty jde do `dilna/out/research/<fragmentId>.json`; na výstup jde jen výtah (§3d krok 6).

S `--requirement rq_…` je to rešerše výslechu (docs/navrhy/2026-10-30-vyslech-srdce.md §3.2, §8): před stolem se
ověří strop ceny požadavku (vyčerpaný = `brief_research_spent` a nic se nespustí), po stole se cena, výtah a ověřené
zdroje přičtou ke spisu (`intake_briefs.cost_usd`). Spis patří prostoru tokenu srdce (`OPORA_WORKSPACE`), ne prostoru
schránky. Bez `--requirement` se příkaz chová jako dřív.
"""
import json
import os
import shutil
import time
from pathlib import Path

try:
    import opora_research_map
    import research_browser
    import research_desk
    import research_fetch
    import research_verify
except ImportError:  # v testech moduly balíčku
    from backend.brain_opora.heart import (
        opora_research_map,
        research_browser,
        research_desk,
        research_fetch,
        research_verify,
    )

ROOT_TITLE = "Výzkum srdce"
ROOT_TEXT = "Kořen výzkumů a duelů srdce (docs/brain-heart.md §3c). Není to zadání ke stavbě."
ROOT_DISCIPLINE = "ai"  # kořen schránky nese disciplínu vždy
REA_MCP = "rea-mcp.json"  # v `dilna/`, píše ho command.write_config (kopie .agent-office/rea-mcp.json)
RESEARCH_DATA = Path("data") / "research"  # v dílně: data/research/<fragmentId>/ (cíle, gather/, cache/)
RESEARCH_OUT = Path("out") / "research"  # v dílně: out/research/<fragmentId>.json (digest a fakta pro skripty)
BROWSER_ENV = "OPORA_RESEARCH_BROWSER"
NT_BROWSERS = ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe")
UNIX_BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge", "microsoft-edge")
BUDGET, MAX_EVIDENCE = 600, 6
BRIEF_RESEARCH = "/api/brain/heart/brief/research"


def find_browser(environ=None, which=shutil.which, nt=None, exists=os.path.isfile):
    """Absolutní cesta k Chrome/Edge pro REA: env `OPORA_RESEARCH_BROWSER`, na Windows Program Files, jinde `which`."""
    environ = os.environ if environ is None else environ
    if environ.get(BROWSER_ENV):
        return environ[BROWSER_ENV] if exists(environ[BROWSER_ENV]) else None
    if os.name == "nt" if nt is None else nt:
        roots = [environ.get(key) for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        for root in dict.fromkeys(filter(None, [*roots, "C:\\Program Files", "C:\\Program Files (x86)"])):
            for name in NT_BROWSERS:
                if exists(path := os.path.join(root, *name.split("/"))):
                    return path
        return None
    return next(filter(None, map(which, UNIX_BROWSERS)), None)


def heart_root(tool, scope):
    """Kořen „Výzkum srdce“ (`scopeNodeId: ""`); založí se jednou."""
    for root in tool.call("GET", "/api/brief-vault", query=scope).get("roots") or []:
        if root.get("title") == ROOT_TITLE and root.get("scopeNodeId") == "" and root.get("kind") == "brief":
            return root["id"]
    made = tool.call("POST", "/api/brief-vault", {**scope, "op": "create", "title": ROOT_TITLE, "text": ROOT_TEXT,
                                                   "scopeNodeId": "", "discipline": ROOT_DISCIPLINE,
                                                   "note": "Kořen výzkumů srdce."})
    return made["fragment"]["id"]


def vault_fields(result, at):
    """`(pole research-update, digest)`: verdikt, jistota, digest jako `approach` a ≤ 6 ověřených URL jako důkazy.
    Schránka bere za doklad verdiktu jen URL: verdikt jiný než `unverified` bez ověřeného URL se zapíše jako
    `unverified` a tvrzení syntézy zůstane v `claimed` (i v textu)."""
    digest, evidence = dict(result["digest"]), []
    for fact in result["facts"]:
        url = fact.get("source") or ""
        if (fact.get("verified") in research_verify.FACT and research_fetch.is_url(url) and len(evidence) < MAX_EVIDENCE
                and url not in {item["url"] for item in evidence}):
            evidence.append({"url": url[:2048], "title": (fact.get("claim") or url)[:300],
                             "quote": (fact.get("quote") or "")[:2000], "accessedAt": at})
    if digest.get("verdict") != "unverified" and not evidence:
        digest.update(verdict="unverified", claimed={**(digest.get("claimed") or {}), "verdict": digest.get("verdict")})
    return ({"verdict": digest["verdict"], "confidence": digest.get("confidence") or "", "evidence": evidence,
             "approach": research_desk.render_approach(digest), "status": "done"}, digest)


def summary(fragment_id, digest, stats, out):
    """Výtah pro srdce (§3d krok 6): verdikt, `next`, vrstvy, řezy, hypotézy, fakta ověřená/tvrzená, cena, čas."""
    result = {"fragmentId": fragment_id, "verdict": digest["verdict"], "confidence": digest.get("confidence") or "",
              "next": digest["next"], "nextWhy": digest.get("nextWhy", "")[:300],
              "layers": [f"{name}: {layer['essence'][:160]} → {layer['recommended'][:160]}"
                         for name, layer in digest["layers"].items()],
              "slices": [item["title"] for item in digest["slices"]],
              "hypotheses": [f"{item['claim'][:160]} – ověřit: {item['check'][:160]}" for item in digest["hypotheses"][:3]],
              "facts": f"{stats['verified']}/{stats['claimed']}", "costUsd": stats["costUsd"],
              "seconds": stats["seconds"], "out": out}
    if digest.get("claimed"):
        result["claimed"] = digest["claimed"]
    if stats.get("skipped"):
        result["skipped"] = stats["skipped"][:6]
    return result


def brief_scope(tool, requirement):
    """Tělo volání stropu rešerše: projekt a prostor tokenu srdce (ne `--workspace` schránky) a požadavek."""
    return {"project": tool.env("OPORA_PROJECT"), "workspace": tool.env("OPORA_WORKSPACE"), "requirement": requirement}


def spend(tool, requirement, fragment_id, digest, fields, cost):
    """Přičte cenu a výtah rešerše ke spisu požadavku; selhání nezahodí hotový výzkum, jen se vrátí v `brief`."""
    body = {**brief_scope(tool, requirement), "costUsd": cost, "fragmentId": fragment_id,
            "digest": f"{digest.get('verdict')}/{digest.get('next')}: {digest.get('nextWhy', '')}"[:300],
            "sources": [item["url"] for item in fields["evidence"]]}
    try:
        return tool.call("POST", BRIEF_RESEARCH, body)
    except tool.Failure as failure:
        return {"error": failure.payload.get("error"), "code": failure.payload.get("code")}


def research(args, tool):
    """`research`: fragment výzkumu, výzkumný stůl a zápis výsledku do schránky a dílny; vypíše jen výtah.
    S `--requirement` nejdřív strop rešerše požadavku a po stole přičtení ceny (`brief` ve výtahu)."""
    requirement = getattr(args, "requirement", None)
    if requirement:
        tool.call("POST", BRIEF_RESEARCH, brief_scope(tool, requirement))  # vyčerpaný strop = Failure s hintem
    scope, dilna, browser = tool.scope(), tool.DILNA.resolve(), find_browser()
    mcp = dilna / REA_MCP
    if browser and not mcp.is_file():
        raise tool.Failure({"error": f"Chybí {REA_MCP}.", "code": "rea_mcp_missing",
                            "hint": "Konfiguraci REA zapisuje dávka srdce do dilna/ před každou dávkou."})
    claude = research_desk.need_claude(tool)
    targets = [target.strip() for target in args.target if target.strip()]
    text = args.question + ("\n\nCíle: " + ", ".join(targets) if targets else "")
    made = tool.call("POST", "/api/brief-vault", {**scope, "op": "research", "fragmentId": args.fragment or heart_root(tool, scope),
                                                  "title": args.title, "text": text, "question": args.question[:1000],
                                                  "status": "running"})
    fragment, started = made["fragment"], time.time()
    result = research_desk.run_desk(args.question, targets, runner=tool._execute, claude=claude,
                                    source_root=os.environ.get("OPORA_SOURCE_ROOT") or None,
                                    data_dir=dilna / RESEARCH_DATA / fragment["id"],
                                    deep=args.deep, layers=getattr(args, "layer", None) or (), browser=browser,
                                    mcp_path=mcp, budget=BUDGET, chrome=research_browser.enabled())
    at = tool.now()
    fields, digest = vault_fields(result, at)
    research_batch = opora_research_map.batch(result, fragment["id"], args, at)
    research_batch["continuation"] = {"researchId": research_batch["operations"][0]["id"],
                                       "sourceFragmentId": fragment["id"], "sourceRevision": fragment["revision"],
                                       "finalization": fields}
    out = dilna / RESEARCH_OUT / f"{fragment['id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Save before either network write. The immutable batch is replayable without paying for another research run.
    out.write_text(json.dumps({"fragmentId": fragment["id"], "question": args.question, "targets": targets,
                               **result, "scope": scope, "researchBatch": research_batch},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    stats = result["stats"]
    # The research already incurred cost, even if later persistence fails.
    tool.log_run("research", [fragment["id"]], 0, int((time.time() - started) * 1000), stats["calls"], stats["costUsd"])
    spent = spend(tool, requirement, fragment["id"], digest, fields, stats["costUsd"]) if requirement else None
    try:
        imported = tool.call("POST", opora_research_map.API, {**scope, **research_batch})
    except tool.Failure as failure:
        raise tool.Failure({**failure.payload, "out": str(out), "scope": scope,
                            "hint": f"Výzkum je uložen. Opakujte research-map import --file {out}; "
                                    "výzkum znovu nespouštějte."}) from failure
    try:
        opora_research_map.finalize(research_batch["continuation"], tool, scope)
    except tool.Failure as failure:
        raise tool.Failure({**failure.payload, "out": str(out), "scope": scope,
                            "hint": f"Mapa je uložená a čeká na dokončení. Opakujte research-map import --file {out}; "
                                    "výzkum znovu nespouštějte."}) from failure
    result = summary(fragment["id"], digest, stats, (Path(tool.DILNA.name) / RESEARCH_OUT / out.name).as_posix())
    result["researchIds"] = [card["id"] for card in imported["cards"]]
    result["scope"] = scope
    if requirement:
        result["brief"] = spent
    return result
