"""Tvar karty z fragmentu Schránky v dávce `/api/canvas-plan` (docs/schranka-neurony.md §4 bod 3).

Jediné pravidlo, jak z fragmentu vzniká karta (převzato beze změny chování z dřívějšího frontendového
`vault-plan.ts`): název `[task] …`, `card.status: draft`, `card.layer` podle disciplíny (§2), bloky z přímých
podfragmentů druhu `brief` (nejvýš 36 u disciplín se závěrečnými bloky, jinak 40) a u disciplín s „ano“
v posledním sloupci §2 navíc čtyři závěrečné bloky logiky, `fragmentRef` na fragment a podfragmenty (≤ 50).
Text zadání se do karty nekopíruje: agent ho dostane doslovně v node-brief. Nově karta nese `spec.goal` =
`done` z brány `synthesized`, `spec.acceptance` = typ mikrokroku + `done` a (je-li `nonGoals`) `spec.non_goals` =
odrážky `- …` (K14).

Název karty je `[task] <název fragmentu>: <první věta done ≤ 80 znaků>`. Zdroje bloků v pořadí (§12, K12):
(a) `steps` z brány `synthesized`, když je karta za fragment, který bránu nese (F jako list; karty za děti F ji
nedostanou, kroky patří mikrokroku F); (b) přímé podfragmenty `brief`; (c) kroky `approach` posledního hotového
výzkumu (`research` se `status: done`, poslední v pořadí `ord`): číslované řádky nebo odrážky (bez nich neprázdné
řádky), nejvýš `MAX_STEPS`. U (a) i (c) nese poslední krok podmínku `done` ze `synthesized`. Závěrečné bloky logiky
zůstávají za nimi. `card.layer` = `layer` ze `synthesized`, jinak vrstva disciplíny (§2).

Spustitelná buňka (docs/schranka-bunka.md §3 bod 2): nese-li `synthesized` `checks`, karta za fragment s bránou
(`lead`) dostane `checks` (kopie `{id, command}`) a `goal_mode: "until_checks_pass"`; bez `checks` beze změny.
Existující kartě je `extend` nepřenáší: jsou to chráněná pole (`backend/canvas/protected_fields.py`), mění je jen
člověk; karta drží kontroly z kola 1 a další kola je musí nést beze změny (`brief_vault_cell.same_checks`).
"""

import re

from backend.editor.brief_vault.brief_vault_disciplines import has_logic_blocks, layer_of

MAX_REFS = 50
MAX_BLOCKS = 40
MAX_STEPS = 36
FIRST_SENTENCE = 80
MAX_CONDITION = 4000  # limit podmínky bloku (MAX_TEXT ve validaci stavu Desktop v3); `done` ≤500 se vejde celé
STEP = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.*\S)\s*$")

# Čtyři závěrečné bloky karty logiky v pevném pořadí; frontend se napojí až na hotovou komponentu.
LOGIC_BLOCKS = (
    {"title": "Funkce a metody", "text": "Jaké funkce a metody vzniknou, jejich vstupy a výstupy.",
     "condition": "Podpisy a odpovědnost každé funkce jsou zapsané."},
    {"title": "Spolupráce", "text": "Jak si funkce předávají data a v jakém pořadí, včetně tabulek a API, kterých se dotknou.",
     "condition": "Tok dat mezi funkcemi je popsaný."},
    {"title": "Test částí", "text": "Každá funkce má vlastní test.", "condition": "Testy jednotlivých částí prošly."},
    {"title": "Komponenta", "text": "Z prošlých částí se složí funkční celek s testem celku.",
     "condition": "Komponenta funguje jako celek a test celku prošel.",
     "ports": [{"ref": "frontend", "label": "Komponenta hotová → frontend"}]},
)


def clip(text, limit):
    """Zkrácení jako ve frontendu: nad limit `limit − 1` znaků bez koncových mezer a výpustka."""
    return text[:limit - 1].rstrip() + "…" if len(text) > limit else text


def first_sentence(text):
    """První věta textu (do první tečky, otazníku či vykřičníku před mezerou nebo koncem), nejvýš 80 znaků."""
    found = re.match(r"\s*(.*?[.!?])(?:\s|$)", text, re.DOTALL)
    return clip(" ".join((found.group(1) if found else text).split()), FIRST_SENTENCE)


def approach_steps(approach):
    """Kroky postupu výzkumu: položky číslovaného seznamu či odrážek (pokračovací řádek se připojí k položce, text
    před prvním bodem je úvod, ne krok); postup bez seznamu = neprázdné řádky. Nejvýš `MAX_STEPS`."""
    lines = [line for line in approach.splitlines() if line.strip()]
    if not any(STEP.match(line) for line in lines):
        return [line.strip() for line in lines][:MAX_STEPS]
    steps = []
    for line in lines:
        found = STEP.match(line)
        if found:
            steps.append(found.group(1))
        elif steps:
            steps[-1] += " " + line.strip()
    return steps[:MAX_STEPS]


def clip_words(text, limit):
    """Zkrácení na hranici slova s výpustkou; nikdy uprostřed slova (text do `limit` znaků zůstává celý)."""
    if len(text) <= limit:
        return text
    head = text[:limit - 1]
    if not text[limit - 1].isspace():
        cut = max(head.rfind(" "), head.rfind("\n"), head.rfind("\t"))
        head = head[:cut] if cut > 0 else head
    return head.rstrip() + "…"


def _step_blocks(steps, synthesized, room):
    """Kroky jsou text, nebo `{text, condition}`; vlastní `condition` bloku má přednost, poslední krok bez ní nese celé `done`."""
    chosen = steps[:min(room, MAX_STEPS)]
    blocks = []
    for number, step in enumerate(chosen, start=1):
        text, own = (step["text"], step.get("condition")) if isinstance(step, dict) else (step, None)
        condition = own or (synthesized["done"] if number == len(chosen) else f"Krok proveden: {text}")
        blocks.append({"title": clip(text, 120), "text": clip(text, 4000), "condition": clip_words(condition, MAX_CONDITION)})
    return blocks


def card_of(ref, parent, row, kids, path, discipline, text_revision, synthesized, steps=(), lead=False):
    """Položka dávky pro jednu kartu; `kids` = přímé podfragmenty `brief` (řádky), `path` = názvy od kořene,
    `steps` = kroky postupu posledního hotového výzkumu (záloha), `lead` = karta za fragment s bránou `synthesized`
    (jen ona bere `synthesized.steps`)."""
    closing = [dict(block, ports=[dict(port) for port in block["ports"]]) if "ports" in block else dict(block)
               for block in LOGIC_BLOCKS] if has_logic_blocks(discipline) else []
    room = MAX_BLOCKS - len(closing)
    planned_steps = list(synthesized.get("steps") or []) if lead else []
    use_kids = bool(kids) and not planned_steps
    if use_kids:
        from_kids = [{"title": clip(kid["title"], 120),
                      "text": "Podfragment ze schránky; doslovný text v node-brief.fragments.",
                      "condition": clip(f"Splněno podle podfragmentu „{kid['title']}“.", 400)} for kid in kids[:room]]
    else:
        from_kids = _step_blocks(planned_steps or list(steps), synthesized, room)
    card = {"status": "draft"}
    layer = synthesized.get("layer") or layer_of(discipline)
    if layer:
        card["layer"] = layer
    text = (f"Zadání karty žije ve schránce zadání: fragment „{clip(row['title'], 120)}“ (revize textu r{text_revision})"
            + (f" a {len(kids)} podfragmentů jako bloky" if use_kids else "")
            + ". Doslovný text dostane agent v node-brief (sekce fragments); sem se nekopíruje.")
    spec = {"goal": synthesized["done"], "acceptance": f"{synthesized['type']}: {synthesized['done']}"}
    if synthesized.get("nonGoals"):
        spec["non_goals"] = "\n".join(f"- {item}" for item in synthesized["nonGoals"])
    checks = [{"id": item["id"], "command": item["command"]} for item in synthesized.get("checks") or []] if lead else []
    return {
        **({"checks": checks, "goal_mode": "until_checks_pass"} if checks else {}),
        "ref": ref,
        "kind": "node",
        "parent": parent,
        "name": clip(f"[task] {row['title']}: {first_sentence(synthesized['done'])}", 160),
        "purpose": clip("Zadání ze schránky: " + " › ".join(path), 1000),
        "text": text,
        "card": card,
        "spec": spec,
        "fragmentRef": [{"fragmentId": item["fragment_id"]} for item in [row, *kids][:MAX_REFS]],
        "blocks": [{"ref": f"b{number}", **block} for number, block in enumerate([*from_kids, *closing], start=1)],
    }
