# Hooky: co hlídají a jak se k nim chovat

Kdy mě číst: běžíš v relaci Claude Code s hookem OPORA a nástroj ti byl zamítnut
(`permissionDecision: deny`, `stopReason`), nebo ti hook do kontextu vložil „Aktuální verze zadání“.

Hook váže relaci Claude Code na jednu kartu. Vazbu, řízení (pauza, stop) a instalaci do VS Code
nastavuje **jen člověk** v UI (záložka Kód → Hook). Agent hook nenastavuje ani neobchází.

## Co hook dělá při každém nástroji

| Situace | Výsledek | Co udělat |
|---|---|---|
| Zápis (`Edit`, `Write`, …) a revize zadání není potvrzená | deny + kontext zadání | přečti cíl, mimo rozsah a přijetí v důvodu, pak spusť přesný příkaz ACK z kontextu |
| Cesta mimo `allowedPaths` nebo control soubor (`protected`) | deny | pracuj jen v povolených cestách; potřebuješ jinou → napiš člověku |
| Nástroj bez konkrétní cesty u scoped nástroje | deny | uveď konkrétní relativní cestu |
| `Bash` mimo přesný privátní příkaz klienta | deny | v hookované relaci Bash nespouštěj; použij povolené příkazy níže |
| `Grep` / `Glob` bez povolení textového hledání | deny | hledej přes LSP / semantic příkaz klienta |
| vyčerpaný rozpočet tool calls, pauza, stop, uzavřená karta | `continue: false` | skonči a předej stav v `agent-workspace` / výstupu |

## Povolené příkazy klienta (přesně podle kontextu hooku)

Kontext hooku uvádí celý prefix příkazu (`python -I … opora_hook.py --client …`). Za něj smí jen:

- `ack <revize>`: potvrdí aktuální revizi zadání (bez ACK se nezapisuje),
- `code-query <typescript|python> <definition|references|hover|documentSymbols> "<cesta>" <řádek> <znak>`: LSP,
- `semantic "<cesta>" "<dotaz česky>"`: sémantické hledání v povolené cestě,
- `memory "<dotaz>"`: paměť role karty.

Při změně zadání (nová revize) hook zápisy znovu zastaví, dokud nepotvrdíš novou revizi. Přečti
změnu, nesmíchej starou práci s novým zadáním. Události hooku vidí člověk v UI (pravdivá observabilita).
