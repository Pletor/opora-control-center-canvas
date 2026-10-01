# Upřesňující prompt: karta na plátně je zadání pro model, ne chatbot flow

Použití: vlož na začátek zadání pro Claude Code, kdykoli se pracuje na kartě, blocích, portech, vazbách, balíčku `node-brief` nebo výstupu `agent-output`. Kontrakt: `docs/karta-pro-agenty.md`.

```
<context>
Repo: Opora Control Center Canvas (frontend React 19 + @xyflow/react 12, backend FastAPI, data v Desktop v3 stavu a v opora-canvas.json). Pravidla: CLAUDE.md, docs/pravidla-struktury.md. Kontrakt karty: docs/karta-pro-agenty.md. Ten kontrakt kód provádí, nemění.

Plátno NENÍ Manychat. Manychat byl jen vizuální předloha (karta složená z bloků, tlačítka jako porty, postranní panel). Cíl je jiný: každá karta je zadání, které si LLM stáhne jako jeden JSON (GET /api/desktop-v3/node-brief) a od začátku do konce vypracuje, a pak vrátí JSON (POST /api/desktop-v3/agent-output). Uživatel karty je model, ne zákazník v chatu.
</context>

<task>
[SEM KONKRÉTNÍ ÚKOL: který dílek, který soubor, jaké chování.]
</task>

<constraints>
MUSÍ: každý prvek karty má jméno a je čitelný bez pohledu na obrazovku (goal, definitionOfDone, boundaries, rules, actions/pipeline, blocks s porty, vazby s report poli log/summary/handoff/improvements/errors, done). Model se nikdy nemá dovozovat význam z pozice nebo barvy.
MUSÍ: pět pohledů se v kartě potkají: Prompt (cíl, hotovo, hranice), Kontext (podklady, pravidla, rozhodnutí, zprávy z příchozích vazeb), Harness (akce v pořadí, kroky, stop podmínky, outputContract), Graf (odkud a kam vazby, z jakého bloku a portu, co je v hloubce), Smyčka (stav bloků open→met/unmet, větvení, zpráva agenta na vazbě, navržené a potvrzené uzavření karty). Když některý pohled v kartě chybí, doplň ho podle kontraktu, ne vlastní vynález.
MUSÍ: přetahovat po plátně jde jen hlavní karta; bloky, porty, tlačítka a vazby jsou k ní napevno.
MUSÍ: agent smí uzavření karty jen navrhnout; potvrzuje člověk. Aplikace žádný model nespouští.
MUSÍ: frontend podle pravidla dílků (rodič ukládá, dílek bublá), CSS v BEM s příběhovým komentářem, test vedle logiky; backend router tenký, validace fail-closed, test vedle modulu.
NESMÍ: přidávat chatové koncepty (24h okno, quick reply, delay, kontakty, tagy zákazníků). NESMÍ přidávat závislosti, měnit kontrakt, commitovat.
NESMÍ: hlásit hotovo bez výstupu `uv run pytest backend`, `npm test`, `npm run build`.
</constraints>

<output_format>
1. Seznam změněných souborů s jednou větou, co v nich vzniklo.
2. Výstup tří ověřovacích příkazů (souhrnné řádky).
3. Body kontraktu, které nešlo splnit přesně, a proč. Jinak „kontrakt splněn beze změn“.
</output_format>
```

🎯 Target: Claude Code (Opus 5 / Fable 5), 💡 Ukotvuje každé zadání ke kontraktu a pěti pohledům, aby implementace kopírovala potřeby modelu čtoucího plátno, ne vzhled Manychatu.
