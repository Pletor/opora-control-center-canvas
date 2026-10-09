"""Pipeline karty (port „pipeline“): autonomní sled etap práce, testů, review, oprav a kritiků.

Stav uzlu `stages = {profile, items, routedBy?, reason?}`. Etapa je
`{id, kind, lens, title, brief, status, note, by, approved, doneBy, at, retryOf?}`.
Proces určuje ROUTER (orchestrátor) přes `POST /api/desktop-v3/pipeline` a každou etapu dělá
nová relace agenta; člověk jen sleduje a jedním klikem přepne profil. Pravomoci:
  - aditivní změna je autonomní: agent smí přidat etapy (platí hned, `by: "agent"`);
  - agent smí přestavět profil, jen dokud je vše `todo` a pipeline nesestavil člověk;
  - ubírající změna (odebrat, přeskládat, upravit definici, `skipped`) patří jen člověku;
  - podlaha: pipeline od agenta má review a kritika hacker, [task] karta a karta s kontrolami i test.
Stav etapy hlásí agent jen přes agent-output (`apply_reports`) s neprázdnou předávkou `note`.
Selhaný test, review nebo kritik sám vloží opravu a opakování (`retryOf`); po `MAX_RETRIES` smyčkách
pipeline čeká na člověka. Kritici, kteří jdou po sobě, tvoří kolo: odevzdávají se v libovolném pořadí
(paralelně), jakmile jsou předchozí etapy uzavřené; selže-li jich v kole víc, vznikne jedna společná
oprava za kolem a opakování každého selhaného kritika. Review a kritik selhávají jen na blokátor
(`BLOCKER`); ostatní nálezy jsou podněty k dalšímu vývoji (`card_ideas.py`), které etapu nezastaví. Zaseknutou etapu (selhaná bez opakování) znovu zařadí `retry_stuck`. `approved: false` je jen starší zápis návrhu; nové etapy jsou platné.
"""

import uuid

from backend.canvas.graph import valid_id

KINDS = ("work", "test", "review", "fix", "critic")
# Tři kritici: hodný uživatel (dělá, co má), vyčuraný (zkratky, nedodělky, obcházení), hacker (útok).
LENSES = ("user", "sly", "hacker")
STATUSES = ("todo", "doing", "passed", "failed", "skipped")
PROFILES = ("goal", "code", "design", "security", "testing", "research", "custom")
AUTHORS = ("human", "agent")
STAGE_KEYS = {"id", "kind", "lens", "title", "brief", "status", "note", "by", "approved", "doneBy", "at"}
STAGE_KEY_SETS = (STAGE_KEYS, STAGE_KEYS | {"retryOf"})
PIPELINE_KEY_SETS = ({"profile", "items"}, {"profile", "items", "routedBy", "reason"})
DEFINITION = ("kind", "lens", "title", "brief")
# Etapy, které hodnotí cizí práci: nesmí je uzavřít autor práce ani opravy.
INDEPENDENT = ("review", "critic")
AUTHORING = ("work", "fix")
RETRIED = ("test", "review", "critic")
REPORT_KEYS = {"id", "status", "note"}
AGENT_STATUSES = ("doing", "passed", "failed")
TEMPLATE_KEYS = {"kind", "lens", "title", "brief"}
MAX_STAGES = 40
# Dvě kola oprav: na kartě 2.43 kritici čtyři kola po sobě našli další okrajový případ; pak rozhodne člověk.
MAX_RETRIES = 2
MAX_TITLE = 200
MAX_TEXT = 4000
MAX_AGENT = 120

# Pravidlo blokátor vs. podnět: proces se nesmí cyklit na okrajových nálezech (karta 2.43).
BLOCKER = ("failed JEN pro blokátor: rozbije MVP nebo proces aplikace, ztráta či únik dat, bezpečnost, "
           "regrese běžného vstupu proti předchozímu chování. Vše ostatní = passed + položka do output.ideas "
           "(podnět k dalšímu vývoji).")
LENS_BRIEF = {
    "user": "Projdi výsledek jako hodný uživatel/agent: dělej, co máš, klikej, jak se má. Funguje hlavní cesta bez překvapení?",
    "sly": "Jako vyčuraný: hledej nedodělky, část místo celku, obcházení místo práce, N/A bez důvodu a testy, které nic neověřují.",
    "hacker": "Jako hacker: napadni proces i data — vstupy, oprávnění, padělání identity, souběh, mazání. Nenech kámen na kameni.",
}
LENS_TITLE = {"user": "Kritik: hodný uživatel", "sly": "Kritik: vyčuraný", "hacker": "Kritik: hacker"}
GOAL_TEST = "GOAL: spouštěj kontroly karty, dokud všechny neprojdou; každý běh zapiš do evidence.checksRun."


def _t(kind, title, brief="", lens=""):
    return {"kind": kind, "lens": lens, "title": title, "brief": brief}


def _critic(lens, title=None, brief=None):
    return _t("critic", title or LENS_TITLE[lens], (brief or LENS_BRIEF[lens]) + " " + BLOCKER, lens)


def _review(title, brief):
    return _t("review", title, brief + " " + BLOCKER)


CRITICS = [_critic("user"), _critic("sly"), _critic("hacker")]
# Šablony profilů: jediný zdroj pravdy pro router i UI (GET /api/desktop-v3/pipeline-profiles).
TEMPLATES = {
    "goal": [
        _t("work", "Práce k cíli", "Implementuj zadání karty proti kontrolám GOAL."),
        _t("test", "Kontroly GOAL", GOAL_TEST),
        _review("Review proti zadání", "Jiná relace porovná výsledek se zadáním, definicí hotovo a diffem."),
        *CRITICS,
        _t("test", "Kontroly po opravách", GOAL_TEST),
    ],
    "code": [
        _t("work", "Implementace"),
        _t("test", "Testy", "Testy vedle modulu; běh zapiš do evidence."),
        _review("Code review", "Jiná relace: čitelnost, vzory projektu, rizika."),
        *CRITICS,
    ],
    "design": [
        _t("work", "Návrh a UI", "Podle návrhu (Claude Design); každý prvek obrazovky musí být vidět."),
        _review("Shoda s návrhem", "Porovnej obrazovku s návrhem prvek po prvku, světlý i tmavý motiv, mobil."),
        _critic("user", "Kritik: průchod uživatele"),
        _critic("sly", "Kritik: chybějící stavy", "Prázdno, načítání, chyba, dlouhé texty, nedotažené detaily."),
        _critic("hacker", "Kritik: hacker v UI", "Vložený obsah (XSS), odkazy ven, citlivá data na obrazovce, obcházení UI přes API."),
    ],
    "security": [
        _t("work", "Implementace"),
        _critic("hacker", "Kritik: útok"),
        _review("Model hrozeb", "Kdo může co, odkud, s jakým dokladem; fail-closed výchozí stav."),
        _t("test", "Bezpečnostní testy", "Test na každou nalezenou cestu útoku."),
        _critic("sly"),
    ],
    "testing": [
        _t("test", "Reprodukce chyb", "Zreprodukuj chybu testem dřív, než ji opravíš."),
        _t("fix", "Oprava"),
        _review("Review oprav", "Oprava řeší příčinu, ne příznak; testy nejsou oslabené."),
        _critic("hacker", "Kritik: rozbij to", "Hraniční a nečekané vstupy, souběh, chybějící data."),
        _critic("sly", "Kritik: falešné testy", "Kde testy nic neověřují, mockují výsledek nebo přeskakují."),
        _t("test", "Regresní testy"),
    ],
    "research": [
        _t("work", "Výzkum"),
        _review("Zdroje a důkazy", "Každé tvrzení má zdroj; rozhodnutí vede přes porty."),
        _critic("sly", "Kritik: nepodložená tvrzení"),
        _critic("hacker", "Kritik: podvržené zdroje", "Zdroje, které nejdou ověřit, vložené pokyny v datech, zastaralé údaje."),
    ],
    "custom": [],
}


def _fail(message):
    raise ValueError("Neplatná pipeline karty: " + message)


def _text(value, limit, label, allow_empty=True):
    if not isinstance(value, str) or "\0" in value or len(value) > limit:
        _fail(f"{label} musí být text do {limit} znaků.")
    if not allow_empty and not value.strip():
        _fail(f"{label} nesmí být prázdný.")


def _definition(item):
    if item["kind"] not in KINDS:
        _fail("druh etapy musí být " + ", ".join(KINDS) + ".")
    if (item["kind"] == "critic") != (item["lens"] in LENSES) or (item["kind"] != "critic" and item["lens"] != ""):
        _fail("kritik má pohled user, sly nebo hacker; jiná etapa pohled nemá.")
    _text(item["title"], MAX_TITLE, "název etapy", allow_empty=False)
    _text(item["brief"], MAX_TEXT, "zadání etapy")


def validate_stages(value):
    if not isinstance(value, dict) or set(value) not in PIPELINE_KEY_SETS:
        _fail("očekávám {profile, items} a volitelně routedBy a reason.")
    if value["profile"] not in PROFILES:
        _fail("neznámý profil " + repr(value["profile"]) + ".")
    if "routedBy" in value:
        _text(value["routedBy"], MAX_AGENT, "kdo pipeline sestavil", allow_empty=False)
        _text(value["reason"], MAX_TEXT, "důvod pipeline")
    items = value["items"]
    if not isinstance(items, list) or len(items) > MAX_STAGES:
        _fail(f"items musí být pole nejvýše {MAX_STAGES} etap.")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) not in STAGE_KEY_SETS:
            _fail("etapa má neplatná pole.")
        if not isinstance(item["id"], str) or not valid_id(item["id"]) or item["id"] in seen:
            _fail("etapa má neplatné nebo opakované id.")
        seen.add(item["id"])
        _definition(item)
        _text(item["note"], MAX_TEXT, "poznámka etapy")
        _text(item["doneBy"], MAX_AGENT, "kdo etapu uzavřel")
        _text(item["at"], 40, "čas etapy")
        if item["status"] not in STATUSES:
            _fail("stav etapy musí být " + ", ".join(STATUSES) + ".")
        if item["by"] not in AUTHORS or type(item["approved"]) is not bool:
            _fail("etapa má neplatného původce nebo schválení.")
        if not item["approved"] and item["status"] != "todo":
            _fail("neschválený návrh etapy nemá stav.")
        if "retryOf" in item and item["retryOf"] not in seen:
            _fail("opakování musí odkazovat na dřívější etapu.")
    return value


def new_stage(template, by):
    return {"id": uuid.uuid4().hex, **{key: template[key] for key in DEFINITION}, "status": "todo", "note": "",
            "by": by, "approved": True, "doneBy": "", "at": ""}


def profile_stages(profile, goal, by="agent"):
    """Etapy profilu ze šablon; na GOAL kartě dostane každý test smyčku kontrol."""
    stages = [new_stage(template, by) for template in TEMPLATES[profile]]
    for stage in stages:
        if goal and stage["kind"] == "test" and "GOAL" not in stage["brief"]:
            stage["brief"] = (stage["brief"] + " " + GOAL_TEST).strip()
    return stages


def validate_templates(value):
    if not isinstance(value, list) or len(value) > MAX_STAGES:
        _fail(f"stages musí být pole nejvýše {MAX_STAGES} etap.")
    for item in value:
        if not isinstance(item, dict) or set(item) != TEMPLATE_KEYS:
            _fail("nová etapa má kind, lens, title a brief.")
        _definition(item)
    return value


def active(value):
    """Platné etapy v pořadí; jen ty řídí práci a uzavření (neschválený starší návrh ne)."""
    return [item for item in (value or {}).get("items", []) if item["approved"]]


def _root(item):
    return item.get("retryOf", item["id"])


def resolved(items, position):
    """Etapa je vyřízená, když prošla, byla přeskočena, nebo ji nahradilo pozdější úspěšné opakování."""
    item = items[position]
    if item["status"] in ("passed", "skipped"):
        return True
    return item["status"] == "failed" and any(
        _root(later) == _root(item) and later["status"] in ("passed", "skipped") for later in items[position + 1:])


def open_stages(value):
    items = active(value)
    return [item for position, item in enumerate(items) if not resolved(items, position)]


def current_stage(value):
    """Etapa na řadě: první nevyřízená, která ještě neselhala (selhaná čeká na své opakování)."""
    items = active(value)
    return next((item for position, item in enumerate(items)
                 if not resolved(items, position) and item["status"] != "failed"), None)


def stuck(value):
    """Selhané etapy bez naplánovaného opakování: autonomní smyčka došla, rozhoduje člověk."""
    items = active(value)
    return [item for position, item in enumerate(items)
            if item["status"] == "failed" and not resolved(items, position)
            and not any(_root(later) == _root(item) and later["status"] in ("todo", "doing")
                        for later in items[position + 1:])]


def floor_missing(items, graph_node, card_type):
    """Co chybí do podlahy pipeline od agenta; prázdný seznam = v pořádku."""
    kinds = {(item["kind"], item["lens"]) for item in items}
    missing = []
    if not any(kind == "review" for kind, _ in kinds):
        missing.append("review")
    if ("critic", "hacker") not in kinds:
        missing.append("kritik hacker")
    if (card_type == "task" or graph_node.get("checks")) and not any(kind == "test" for kind, _ in kinds):
        missing.append("test")
    return missing


def summary(value):
    items = active(value)
    current = current_stage(value)
    return {
        "routed": bool(items),
        "profile": (value or {}).get("profile"),
        "current": current and {key: current[key] for key in ("id", "kind", "lens", "title")},
        "finished": len(items) - len(open_stages(value)),
        "total": len(items),
        "stuck": [{"id": item["id"], "title": item["title"], "note": item["note"]} for item in stuck(value)],
    }


def guard_state_write(actor, previous, value):
    """Obecný zápis stavu od ne-člověka smí etapy jen přidat za rozpracovanou část (aditivně);
    profil, pořadí, definici, odebrání a stav etap mění člověk, stav agent hlásí přes agent-output."""
    from backend.canvas.activity_log import HumanRequired

    before = previous or {"profile": "custom", "items": []}
    if value is None:
        if before["items"]:
            raise HumanRequired(actor, "Pipeline karty odebírá jen člověk.")
        return
    if {key: value.get(key) for key in ("profile", "routedBy", "reason")} != \
            {key: before.get(key) for key in ("profile", "routedBy", "reason")} and before["items"]:
        raise HumanRequired(actor, "Profil pipeline mění router přes /api/desktop-v3/pipeline nebo člověk.")
    old = {item["id"]: item for item in before["items"]}
    if [item["id"] for item in value["items"] if item["id"] in old] != [item["id"] for item in before["items"]]:
        raise HumanRequired(actor, "Etapy pipeline odebírá a přeskládává jen člověk.")
    last_started = max((position for position, item in enumerate(value["items"])
                        if item["id"] in old and item["status"] != "todo"), default=-1)
    for position, item in enumerate(value["items"]):
        prior = old.get(item["id"])
        if prior is None:
            if item["by"] != "agent" or item["status"] != "todo" or "retryOf" in item or position < last_started:
                raise HumanRequired(actor, "Agent etapu jen přidá (by: agent, todo) za rozpracovanou část pipeline.")
        elif item != prior:
            raise HumanRequired(actor, "Etapu pipeline mění jen člověk; stav agent hlásí přes agent-output.")


def validate_reports(value):
    if not isinstance(value, list) or len(value) > MAX_STAGES:
        raise ValueError(f"Neplatný výstup agenta: stages musí být pole nejvýše {MAX_STAGES} hlášení.")
    for item in value:
        if not isinstance(item, dict) or set(item) != REPORT_KEYS:
            raise ValueError("Neplatný výstup agenta: hlášení etapy má id, status a note.")
        if not isinstance(item["id"], str) or not valid_id(item["id"]) or item["status"] not in AGENT_STATUSES:
            raise ValueError("Neplatný výstup agenta: etapa má neplatné id nebo stav (doing, passed, failed).")
        _text(item["note"], MAX_TEXT, "poznámka etapy")
        if item["status"] != "doing" and not item["note"].strip():
            raise ValueError("Neplatný výstup agenta: passed i failed nesou předávku další relaci (note).")
    if len({item["id"] for item in value}) != len(value):
        raise ValueError("Neplatný výstup agenta: etapa se v jednom výstupu opakuje.")


def _retries_left(items, stage):
    root = _root(stage)
    return sum(1 for item in items if item.get("retryOf") == root) < MAX_RETRIES


FIX_BRIEF = "Oprav nálezy etapy"


def _fix_brief(stage):
    return f"{FIX_BRIEF} „{stage['title']}“: {stage['note']}"


def _retry(stage):
    return {**new_stage({key: stage[key] for key in DEFINITION}, "agent"), "retryOf": _root(stage)}


def _retry_pair(stage):
    fix = new_stage(_t("fix", f"Oprava: {stage['title']}", _fix_brief(stage)[:MAX_TEXT]), "agent")
    return [fix, _retry(stage)]


def critic_round(items, position):
    """Kolo kritiků: souvislý běh etap `critic` kolem pozice; vrací (první, poslední) index.
    Kritici jednoho kola smí odevzdat v libovolném pořadí (paralelně)."""
    start = end = position
    while start > 0 and items[start - 1]["kind"] == "critic":
        start -= 1
    while end + 1 < len(items) and items[end + 1]["kind"] == "critic":
        end += 1
    return start, end


def _round_fix(item):
    """Společná oprava kola: vložil ji server (by agent, brief z nálezů) a ještě neskončila."""
    return (item["kind"] == "fix" and item["by"] == "agent" and item["status"] in ("todo", "doing")
            and item["brief"].startswith(FIX_BRIEF))


def _queue_retry(stages, stage):
    """Za selhaný test, review či kritika vloží opravu a opakování; po MAX_RETRIES smyčkách už ne (čeká člověk).
    Kritik: oprava jde za celé kolo; další selhaný kritik téhož kola ji jen doplní a přidá své opakování."""
    items = stages["items"]
    if not _retries_left(items, stage):
        return
    position = items.index(stage)
    # Opakování uz naplanovane kdekoli dal (i po opakovanem hlaseni failed teze etapy) se nezdvoji.
    if any(_root(later) == _root(stage) and later["status"] in ("todo", "doing") for later in items[position + 1:]):
        return
    if stage["kind"] != "critic":
        if len(items) + 2 <= MAX_STAGES:
            items[position + 1:position + 1] = _retry_pair(stage)
        return
    after = critic_round(items, position)[1] + 1
    if after < len(items) and _round_fix(items[after]):
        if len(items) + 1 > MAX_STAGES:
            return
        fix = items[after]
        fix["title"] = (fix["title"] + ", " + stage["title"])[:MAX_TITLE]
        fix["brief"] = (fix["brief"] + "\n" + _fix_brief(stage))[:MAX_TEXT]
        insert = after + 1
        while (insert < len(items) and items[insert]["kind"] == "critic" and "retryOf" in items[insert]
               and items[insert]["status"] == "todo"):
            insert += 1
        items[insert:insert] = [_retry(stage)]
    elif len(items) + 2 <= MAX_STAGES:
        items[after:after] = _retry_pair(stage)


def retry_stuck(stages, stage_id):
    """Zaseknutou etapu (selhala, opakování nenaplánováno) znovu zařadí: oprava + opakování za rozpracovanou
    část. Mutuje `stages`; vrací False, když došly smyčky (MAX_RETRIES) a rozhoduje člověk."""
    stage = next((item for item in stuck(stages) if item["id"] == stage_id), None)
    if stage is None:
        raise ValueError("Etapa není zaseknutá (selhaná bez naplánovaného opakování).")
    if stage["kind"] not in RETRIED:
        raise ValueError("Opakovat lze jen etapu test, review nebo kritik.")
    items = stages["items"]
    if not _retries_left(items, stage):
        return False
    if len(items) + 2 > MAX_STAGES:
        raise ValueError(f"Pipeline má nejvýše {MAX_STAGES} etap.")
    last_started = max(position for position, item in enumerate(items) if item["status"] != "todo")
    items[last_started + 1:last_started + 1] = _retry_pair(stage)
    return True


def apply_reports(stages, reports, agent, stamp, graph_node, evidence):
    """Zapíše hlášení agenta do pipeline (mutuje `stages`); poruší-li pořadí, nezávislost nebo GOAL, nezapíše nic."""
    from backend.canvas.card_checks import checks_passed

    if not stages:
        raise ValueError("Karta nemá pipeline; nejprve ji nasměruje router.")
    for report in reports:
        items = active(stages)
        index = {item["id"]: position for position, item in enumerate(items)}
        position = index.get(report["id"])
        if position is None:
            raise ValueError(f"Etapa {report['id']} na kartě není.")
        stage = items[position]
        if report["status"] in ("passed", "failed"):
            # Kritici jednoho kola nečekají na sebe navzájem, jen na etapy před kolem.
            first = critic_round(items, position)[0] if stage["kind"] == "critic" else position
            waiting = [item["title"] for item in items[:first] if item["status"] in ("todo", "doing")]
            if waiting:
                raise ValueError("Etapu nelze uzavřít před předchozími: " + ", ".join(waiting) + ".")
        if report["status"] == "passed":
            if stage["kind"] in INDEPENDENT and any(
                item["kind"] in AUTHORING and item["doneBy"] == agent for item in items
            ):
                raise ValueError(f"Etapu „{stage['title']}“ musí uzavřít jiná relace než ta, která dělala práci nebo opravu.")
            if (stage["kind"] == "test" and graph_node.get("goal_mode") == "until_checks_pass"
                    and not checks_passed(graph_node, evidence)):
                raise ValueError("Test na GOAL kartě projde až s úspěšným během všech kontrol (evidence.checksRun).")
        stage.update(status=report["status"], note=report["note"], doneBy=agent, at=stamp)
        if report["status"] == "failed" and stage["kind"] in RETRIED:
            _queue_retry(stages, stage)


def brief_of(value, graph_node):
    """Pipeline pro node-brief: pořadí, aktuální etapa, předávky a pravidla, podle kterých server hlídá."""
    if not value or not value["items"]:
        return None
    current = current_stage(value)
    items = active(value)
    parallel = []
    if current and current["kind"] == "critic":
        start, end = critic_round(items, items.index(current))
        parallel = [item["id"] for item in items[start:end + 1] if item["status"] in ("todo", "doing")]
    return {
        "profile": value["profile"],
        "routedBy": value.get("routedBy", ""),
        "reason": value.get("reason", ""),
        "current": current and {key: current[key] for key in ("id", "kind", "lens", "title", "brief")},
        # Kritici aktuálního kola, které smí odevzdat jakákoli nezávislá relace v libovolném pořadí.
        "parallel": parallel,
        "stages": [{key: item.get(key, "") for key in ("id", "kind", "lens", "title", "brief", "status", "note", "doneBy", "retryOf")}
                   for item in active(value)],
        "stuck": [{"id": item["id"], "title": item["title"], "note": item["note"]} for item in stuck(value)],
        "goal": graph_node.get("goal_mode") == "until_checks_pass",
        "policy": ["one session = one card + one stage (current); read previous stage notes as handoff",
                   "report stage status only via agent-output.stages [{id, status: doing|passed|failed, note}]; passed/failed need a non-empty note",
                   ("a stage is reported only after all earlier stages were attempted; consecutive critic stages form one round "
                    "and may be reported in any order (in parallel) once the stages before the round are closed (pipeline.parallel)"),
                   ("review and critic: failed ONLY for a blocker = breaks the MVP or the app process, data loss or leak, security, "
                    "regression of common input against previous behaviour; everything else = passed + an item in output.ideas"),
                   "review and critic stages must be passed by a different session than work/fix",
                   "on a GOAL card the test stage passes only with every check green in evidence.checksRun",
                   ("a failed test, review or critic queues a fix and a retry automatically; failed critics of one round share one fix "
                    f"and each gets its own retry; after {MAX_RETRIES} loops a human decides"),
                   "a stuck stage (failed without a queued retry) is requeued by POST /api/desktop-v3/pipeline op retry + stageId",
                   "agents may add stages (POST /api/desktop-v3/pipeline op add); removing, reordering and skipping is human-only",
                   "the card closes only when every stage is passed, skipped by a human, or superseded by a passed retry"],
    }
