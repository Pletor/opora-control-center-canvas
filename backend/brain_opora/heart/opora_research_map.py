"""Standalone, stdlib-only research map client copied beside opora_heart.py.

Batch files contain {key, operations}; project/workspace always come from the heart scope.
Import accepts the durable output of `research` and is safe to retry unchanged.
"""
import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urlparse

try:
    from . import research_alternatives, research_actions
except ImportError:  # Standalone helper copied into the heart's working directory.
    import research_alternatives, research_actions

API = "/api/research"
REFS = ("nodeIds", "questionIds", "ticketIds", "sessionIds", "fragmentIds", "attachmentIds")
RUNTIME_GUIDANCE = """

## Plán po výzkumu: návrh, přijetí a realizace jsou různé kroky
Než oznámíš, že úprava nemá nástroj, použij `python opora_heart.py canvas discover` a
`python opora_heart.py canvas describe ID_SCHOPNOSTI`. Čti skutečný kontrakt, neodhaduj pole.
Volání: `python opora_heart.py canvas invoke ID_SCHOPNOSTI --file dilna/out/input.json`;
zápis navíc se stabilním `--request-id`. Soubor obsahuje jen input kontraktu, scope a autora dodá nástroj.
`ctx plan-of` je orientační projekce, ne podklad pro úplný přepis. Autoritativní zadání čti přes
`node_routes.node_spec` (input node); graf/status přes `canvas_routes.view`; přijetí, digest a revizi stavu
přes `opora_graph_routes.context`. Zachovej ID, původ i ostatní obsah a přečti celé vrácené dokumenty.
Bez přijatého základu lze změnit zadání existujícího uzlu přes `canvas_routes.canvas_plan`:
parentRevision null, aktuální expectedGraphDigest, plan.extend s node @ID, expectedRevision stavu
a spec {expectedRevision dokumentu, fields}. Prázdné files výzkumného kroku jsou nativně přípustné.
Stav card.status existující karty mění `canvas_routes.graph`: úplný aktuální graph se zachovanými ID,
digest a expectedAcceptedHead null. Nejprve describe obou operací; žádné domýšlení podporovaných polí.
Tyto dva zápisy jsou oddělené, nejsou atomické. Každý má vlastní request-id, CAS a plný readback;
při konfliktu zastav a přiznej již uloženou část. Nad přijatým základem používej nativní návrhy pro lidskou
kontrolu, nepřepisuj přijatou autoritu. Omezení příkazu steps neobcházej vymyšlenou cestou.
Pokud člověk žádá plán, samotné `needs_info`, výzkum ani `decide` nejsou uložený návrh plánu.
Zjištěný rozpor (například doména nebo autentizace) blokuje pouze závislé rozhodnutí a realizaci.
Před odpovědí ulož smysluplnou nezávislou část návrhu a explicitní otevřené otázky s podklady;
nepovyšuj neověřený závěr na fakt. Původní ID, existující úkoly a přijatá rozhodnutí zachovej.
Nejdřív čti aktuální pracovní plán (`ctx plan-of --project ID`; výstup ukáže skutečný workspace).
Zápis směruj výslovně do tohoto prostoru: `plan --workspace W --file dilna/out/plan.json --no-accept`.
`plan` nyní výchozím chováním ukládá návrh bez přijetí. `--accept` smíš použít jen při výslovném,
stále platném oprávnění přijmout konkrétní produktové rozhodnutí; žádost o opravu plánovacího systému
ani o vytvoření návrhu není souhlas s realizací produktu. Nevyřešenou doménu, identitu nebo impersonaci
zachovej jako otázku, nespouštěj jejich implementaci. Nad přijatým grafem použij nejprve podporovaný
malý návrh uzlů se spec a vazbami; nepředstírej podporu polí, která server odmítl.
U výsledku rozliš persisted, verified a accepted. O uložení ověřeného návrhu smíš informovat až při
verified:true a readback se skutečnými ID/revizí. Návrh čekající na přijetí není karta již přidaná do
přijaté Struktury. Při plan_readback_failed čti existující proposalId; zápis mohl uspět, nevytvářej kopii.
Plán má stabilní operationId odvozené ze scope a obsahu. Před odesláním se přesný požadavek ukládá do
dilna/out/plan-operations; po timeoutu opakuj stejný příkaz a soubor, vrátí tentýž zápis. Původní revize se
při retry nemění. Konflikt revize vyžaduje nové načtení a vědomý nový návrh s novým --operation-id;
stejné ID s jiným obsahem je chyba. Nové ID nepoužívej jen proto, že předchozí odpověď nedorazila.
Pokud návrh nejde uložit, uveď přesný neúspěšný krok a pokračuj jen v nezávislé práci.

## Rešerše: trvalá paměť problému
Před hledáním čti `python opora_heart.py research-map ls` (hlavičky a významové hrany),
pak `research-map show ID` pro úplný obsah, zdroje a historii. Historie vazby: `research-map show ID --entity edge`.
Nepovažuj hlavičku za celý důkaz.
`research --question Q --title T --topic Přihlášení --topic Logika --node NODE --question-id pq_…`
ukládá všechna zjištění do Rešerše; podle situace přidej --ticket TK --session RELACE nebo --attachment ID.
Téma znamená konkrétní problém, ne kopii celého stromu. Zjištění roztřiď podle významu; design nedokládá backend.
Zápis: `research-map save --file dilna/out/map.json`; soubor {"key":"jedinečný-klíč","operations":[…]}.
Screenshot nejdřív ulož `research-map attach --file dilna/out/login.png`; vrácené attachmentId vlož do
refs.attachmentIds vizuální karty. Soubor je uložen v úložišti Kreslení (GET /api/drawing-files), ne automaticky
vložen do scény. refs.nodeIds odkazuje na související uzel/vrstvu kresby. Zdroj screenshotu dolož v sources.
Operace card: {op:"card",id,expectedRevision:0,title,summary,topicPath:["Přihlášení","UX/UI"],
kind:"visual",content:"úplný rozbor",status:"open",verification:{status:"observed",method:"REA",at:"ISO čas"},
sources:[{ref:"https://…",platform:"rea",quote:"pozorovaný jev",title:"Zdroj",accessedAt:"ISO čas"}],
refs:{nodeIds:[],questionIds:[],ticketIds:[],sessionIds:[],fragmentIds:[],attachmentIds:["ID v Kreslení"]}}.
Aktualizaci nejprve načti; expectedRevision musí být současná revision. Nové ID má expectedRevision:0.
Operace edge: {op:"edge",id,expectedRevision:0,fromId,toId,relation:"continues_to",reason:"UX/UI určuje interakci,
nikoli ověření identity",resolved:"Formulář a jeho stavy jsou navrženy",missing:"Ověřit autentizační mechanismus",
evidenceIds:["ID podkladu"]}. UX/UI → logika vysvětluje odkud, kam a proč; doplň doklady.
Další relation: supports, contradicts, elaborates, option_for, supersedes, resolves. Každá hrana má konkrétní reason.
U resolves i continues_to musí resolved popsat skutečně vyřešenou část a missing zbývající ověření či výslovně
uvést, že v daném rozsahu nic nechybí. Samotné uzavření rozhovoru neznamená vyřešení problému.
Ověření citace znamená shodu se zdrojem, ne automaticky pravdivost výkladu. Rozliš verified, observed,
unverified, false, unreachable, inference, conflict. Návrh ani hrana nejsou schválení člověkem.
Zachovej citace, původní URL (Google je cesta nalezení), čas videa/revizi kódu a ID příloh; nic nedomýšlej.
Do sources ukládej časový úsek videa jako timestamp; u kódu revision a location (soubor a řádky).
Otázky, varianty, rozhodnutí a fakta propojuj. Nejdřív ulož karty a vazby s refs.questionIds/ticketIds/sessionIds;
teprve po potvrzení zápisu odpověz Pletorovi nebo vrať ticket. ID nevymýšlej.
Dlouhou odpověď napiš nástrojem Write do dilna/out/answer.txt a odešli jednoduchým příkazem
`python opora_heart.py pletor-answer --question ID --file dilna/out/answer.txt --ref ID_PODKLADU`.
Nevkládej dlouhý text s citacemi do shellových uvozovek. Soubor se čte jako UTF-8, nejvýš 8000 znaků;
delší úplné podklady patří do Rešerše, odpověď odkazuje na jejich ID.
První nalezenou cestu nepokládej za nejlepší. Porovnej relevantní varianty, jejich doložené výhody,
nevýhody, předpoklady a důsledky pro konkrétní projekt. Rozpory zachovej, chybějící důkaz přiznej.
Přijatou cestu najdi přes `research-map reviews --decision ID`; pouze člověk vytváří záznam posouzení.
Pro převod použij `research-map tasks --review ID --file tasks.json`: soubor obsahuje pouze
{"tasks":[{"ref":"task1","title":"…","goal":"…","acceptance":"…","dependsOn":[]}]};
existující úkol aktualizuj s nodeId, nový nevytvářej jako náhradu existující identity. Volitelný parentId
určuje sektor. Nástroj připne původ problému, rozhodnutí a důkazů do nativního návrhu OporaHubu.
Samotné posouzení výzkumu nepřijímá zadání. Čekej na nativní přijetí návrhu člověkem; stav ukáže
`research-map task-status --review ID`. Potom `research-map reconcile --review ID` doplní zpětné vazby.
Pro problém Kanceláře volej `research-map ticket-branch --ticket ID --feedback ID`; server připne původní
relaci, revizi úkolu a problém. Doplň výzkum a vazbu resolves z řešení na tuto otázku. Odpověz přes
`research-map ticket-answer --ticket ID --feedback ID --card ID --revision N --text "…"`.
Starší ticket-answer --ticket ID zůstává obecným nástrojem; rešeršní cesta používá připnutou revizi.
Změny plánu podléhají dosavadním pravidlům, žádné nové oprávnění nevzniká.
Nemaž historii: operace {op:"archive",entity:"card"|"edge",id,expectedRevision:N,archived:true}.
Starší obsah: research-map show ID --revision N; archiv: research-map ls --archived.
Po chybě uložení opakuj `research-map import --file dilna/out/research/FRAGMENT.json`; výzkum znovu nespouštěj.
"""


def read_file(path, tool):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise TypeError("Očekáván objekt JSON.")
        return value
    except (OSError, ValueError) as error:
        raise tool.Failure({"code": "research_file", "error": str(error), "hint": "Zadejte čitelný soubor JSON."}) from error


def run(args, tool):
    if args.action in research_actions.ACTIONS:
        return research_actions.run(args, tool)
    scope = tool.scope()
    if args.action == "ls":
        return {**tool.call("GET", API, query={**scope, "archived": int(args.archived)}), "scope": scope}
    if args.action == "show":
        query = {**scope, **({"revision": args.revision} if args.revision is not None else {})}
        entity = "edges" if args.entity == "edge" else "cards"
        try:
            return {**tool.call("GET", f"{API}/{entity}/{quote(args.id, safe='')}", query=query), "scope": scope}
        except tool.Failure as error:
            if entity != "cards" or error.payload.get("status") != 404:
                raise
            return {**tool.call("GET", f"{API}/originals/{quote(args.id, safe='')}", query=query), "scope": scope}
    if args.action == "attach":
        return attach(args.file, tool)
    data = read_file(args.file, tool)
    if args.action == "import":
        if data.get("scope") != scope or not isinstance(data.get("researchBatch"), dict):
            raise tool.Failure({"code": "research_scope", "error": "Výstup nepatří aktuálnímu projektu a prostoru.",
                                "hint": "Použijte původní scope a nezměněný výstup research s researchBatch."})
        data = data["researchBatch"]
    if not {"key", "operations"} <= set(data) or set(data) - {"key", "operations", "continuation"}:
        raise tool.Failure({"code": "research_batch", "error": "Soubor dávky vyžaduje key, operations a volitelný continuation.",
                            "hint": "Scope dodává token a prostředí srdce, ne soubor dávky."})
    saved = tool.call("POST", API, {**data, **scope})
    if args.action == "import" and data.get("continuation", {}).get("finalization") is not None:
        saved = {**saved, "finalization": finalize(data["continuation"], tool, scope)}
    return {**saved, "scope": scope}


def finalize(intent, tool, scope):
    """Native CAS only; an advanced original is read back, never rewritten on retry."""
    identifier, revision = intent["sourceFragmentId"], intent["sourceRevision"]
    fields = intent["finalization"]
    route = f"{API}/originals/{quote(identifier, safe='')}"

    def read():
        return tool.call("GET", route, query=scope)

    def already(value):
        actual = value.get("original", {}).get("details", {}).get("research", {})
        if value.get("sourceRevision", 0) > revision and all(actual.get(key) == expected for key, expected in fields.items()):
            return {"sourceRevision": value["sourceRevision"], "alreadyFinalized": True}
        raise tool.Failure({"code": "research_finalization_conflict",
                            "error": "Původní rešerše se změnila a neobsahuje přesný uložený výsledek.",
                            "hint": "Zachovejte výstupní soubor; vyřešte rozdíl původní rešerše, nespouštějte výzkum znovu."})

    current = read()
    if current.get("sourceRevision") != revision:
        return already(current)
    try:
        return tool.call("POST", "/api/brief-vault", {**scope, "op": "research-update", "fragmentId": identifier,
                         "expectedRevision": revision, "note": "Výsledek výzkumného stolu srdce.", **fields})
    except tool.Failure:
        return already(read())  # Includes a committed update whose HTTP response was lost.


def attach(filename, tool):
    """Reuse drawing file store; deterministic content ID makes upload retries harmless."""
    path = Path(filename)
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif"}.get(path.suffix.lower())
    try:
        if not mime or not 0 < path.stat().st_size <= 10 * 1024 * 1024:
            raise ValueError("Screenshot musí být PNG, JPEG, WebP nebo GIF do 10 MB.")
        data = path.read_bytes()
    except (OSError, ValueError, TypeError) as error:
        raise tool.Failure({"code": "research_attachment", "error": str(error),
                            "hint": "Zadejte cestu k existujícímu screenshotu."}) from error
    fid = "research_" + hashlib.sha256(data).hexdigest()
    tool.call("POST", "/api/drawing-file", {**tool.scope(), "file": {
        "id": fid, "mimeType": mime, "dataURL": f"data:{mime};base64," + base64.b64encode(data).decode("ascii")}})
    return {"attachmentId": fid, "scope": tool.scope(), "mimeType": mime}


def stable_id(prefix, *parts):
    raw = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def platform(source, observed=False):
    if observed:
        return "rea"
    host = (urlparse(source).hostname or "").lower()
    for domains, name in ((("youtube.com", "youtu.be"), "youtube"), (("facebook.com", "fb.com"), "facebook"),
                          (("instagram.com",), "instagram"), (("x.com", "twitter.com"), "x"),
                          (("medium.com",), "medium")):
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return name
    return "web" if host else "code"


def batch(result, fragment_id, args, at):
    """Lossless deterministic import: every fact gets its own card, including shared URLs and failed checks."""
    refs = {key: [] for key in REFS}
    for field, arg in (("nodeIds", "node"), ("questionIds", "question_id"), ("ticketIds", "ticket"),
                       ("sessionIds", "session"), ("attachmentIds", "attachment")):
        refs[field] = list(dict.fromkeys(getattr(args, arg, None) or []))
    refs["fragmentIds"] = [fragment_id]
    topic = list(getattr(args, "topic", None) or [args.title])
    root = stable_id("rc_", fragment_id, "result")
    digest = result["digest"]
    operations = [{"op": "card", "id": root, "expectedRevision": 0, "kind": "question", "title": args.title,
                   "summary": digest.get("nextWhy") or args.question, "topicPath": topic,
                   "content": json.dumps({"question": args.question, "digest": digest,
                                          "options": result.get("options", []), "stats": result.get("stats", {})},
                                         ensure_ascii=False, indent=2),
                   "status": "open", "verification": {"status": "inference", "method": "research_digest", "at": at},
                   "sources": [], "refs": refs}]
    for index, fact in enumerate(result["facts"]):
        fid = stable_id("rc_", fragment_id, "fact", index, fact.get("id"))
        state = fact.get("verified") or "unverified"
        method = "rea_observation" if state == "observed" else "source_quote_check"
        # Matching a citation verifies its origin, not the researcher's project-specific interpretation.
        interpretation = fact.get("kind") in ("practice", "risk", "hypothesis", "inference")
        card_state = "inference" if interpretation and state in ("verified", "observed") else state
        source = fact.get("source") or ""
        sources = []
        if source:
            evidence = {"ref": source, "platform": platform(source, observed=state == "observed"), "quote": fact.get("quote") or "",
                        "title": fact.get("claim") or source, "accessedAt": at,
                        "verification": {"status": state, "method": method, "at": at}}
            for field in ("timestamp", "revision", "location", "discoveredVia"):
                if fact.get(field) is not None:
                    evidence[field] = fact[field]
            sources.append(evidence)
        operations.append({"op": "card", "id": fid, "expectedRevision": 0, "kind": "finding",
                           "title": fact.get("claim") or fact.get("id") or "Zjištění",
                           "summary": fact.get("claim") or "Zjištění vyžaduje přečtení detailu.",
                           "topicPath": [*topic, *([fact["layer"]] if fact.get("layer") else [])],
                           "content": json.dumps(fact, ensure_ascii=False, indent=2), "status": "open",
                           "verification": {"status": card_state, "method": method + ("; project interpretation" if interpretation else ""),
                                            "at": at}, "sources": sources, "refs": refs})
        operations.append({"op": "edge", "id": stable_id("re_", root, fid), "expectedRevision": 0,
                           "fromId": fid, "toId": root, "relation": "elaborates",
                           "reason": "Zjištění vzniklo při ověřování této otázky; stav ověření určuje použitelnost podkladu.",
                           "resolved": "", "missing": "", "evidenceIds": [fid]})
    operations.extend(research_alternatives.operations(result, fragment_id, topic, refs, at, stable_id))
    return {"key": "research:" + fragment_id, "operations": operations}
