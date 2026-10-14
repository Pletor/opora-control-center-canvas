"""Tvar karty z fragmentu Schránky v dávce `/api/canvas-plan` (docs/schranka-neurony.md §4 bod 3).

Jediné pravidlo, jak z fragmentu vzniká karta (převzato beze změny chování z dřívějšího frontendového
`vault-plan.ts`): název `[task] …`, `card.status: draft`, `card.layer` podle disciplíny (§2), bloky z přímých
podfragmentů druhu `brief` (nejvýš 36 u disciplín se závěrečnými bloky, jinak 40) a u disciplín s „ano“
v posledním sloupci §2 navíc čtyři závěrečné bloky logiky, `fragmentRef` na fragment a podfragmenty (≤ 50).
Text zadání se do karty nekopíruje: agent ho dostane doslovně v node-brief. Nově karta nese `spec.goal` =
`done` z brány `synthesized` a `spec.acceptance` = typ mikrokroku + `done`.

Název karty je `[task] <název fragmentu>: <první věta done ≤ 80 znaků>`. Fragment bez přímých podfragmentů
`brief` dostane bloky z kroků `approach` posledního hotového výzkumu (`research` se `status: done`, poslední v pořadí
`ord`): číslované řádky nebo odrážky (bez nich neprázdné řádky), nejvýš `MAX_STEPS`; poslední krok nese podmínku
`done` ze `synthesized`. Závěrečné bloky logiky zůstávají za nimi.
"""

import re

from backend.editor.brief_vault.brief_vault_disciplines import has_logic_blocks, layer_of

MAX_REFS = 50
MAX_BLOCKS = 40
MAX_STEPS = 36
FIRST_SENTENCE = 80
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


def _step_blocks(steps, synthesized, room):
    chosen = steps[:min(room, MAX_STEPS)]
    return [{"title": clip(step, 120), "text": clip(step, 4000),
             "condition": clip(synthesized["done"] if number == len(chosen) else f"Krok proveden: {step}", 400)}
            for number, step in enumerate(chosen, start=1)]


def card_of(ref, parent, row, kids, path, discipline, text_revision, synthesized, steps=()):
    """Položka dávky pro jednu kartu; `kids` = přímé podfragmenty `brief` (řádky), `path` = názvy od kořene,
    `steps` = kroky postupu posledního hotového výzkumu (použijí se jen bez `kids`)."""
    closing = [dict(block, ports=[dict(port) for port in block["ports"]]) if "ports" in block else dict(block)
               for block in LOGIC_BLOCKS] if has_logic_blocks(discipline) else []
    from_kids = [{"title": clip(kid["title"], 120),
                  "text": "Podfragment ze schránky; doslovný text v node-brief.fragments.",
                  "condition": clip(f"Splněno podle podfragmentu „{kid['title']}“.", 400)}
                 for kid in kids[:MAX_BLOCKS - len(closing)]] if kids else _step_blocks(
                     list(steps), synthesized, MAX_BLOCKS - len(closing))
    card = {"status": "draft"}
    if layer_of(discipline):
        card["layer"] = layer_of(discipline)
    text = (f"Zadání karty žije ve schránce zadání: fragment „{clip(row['title'], 120)}“ (revize textu r{text_revision})"
            + (f" a {len(kids)} podfragmentů jako bloky" if kids else "")
            + ". Doslovný text dostane agent v node-brief (sekce fragments); sem se nekopíruje.")
    return {
        "ref": ref,
        "kind": "node",
        "parent": parent,
        "name": clip(f"[task] {row['title']}: {first_sentence(synthesized['done'])}", 160),
        "purpose": clip("Zadání ze schránky: " + " › ".join(path), 1000),
        "text": text,
        "card": card,
        "spec": {"goal": synthesized["done"], "acceptance": f"{synthesized['type']}: {synthesized['done']}"},
        "fragmentRef": [{"fragmentId": item["fragment_id"]} for item in [row, *kids][:MAX_REFS]],
        "blocks": [{"ref": f"b{number}", **block} for number, block in enumerate([*from_kids, *closing], start=1)],
    }
