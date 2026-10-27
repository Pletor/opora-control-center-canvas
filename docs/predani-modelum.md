# Předání práce modelům: Opus 5.5, Sonnet 5.5, Fable 5.1

Jak dát současným modelům Claude zadání tak, aby pracovaly správným směrem bez doptávání a bez pálení tokenů. Ověřeno v dokumentaci Anthropic k 2026-10-01; co nebylo ověřeno, je označeno [neověřeno]. Kontrakt karty, ze kterého zadání vzniká, je v [karta-pro-agenty.md](karta-pro-agenty.md), celý postup v [workflow-opora.md](workflow-opora.md).

## Společné pro všechny tři

- **Myšlení je adaptivní a řídí ho effort, ne prompt.** Úroveň `low | medium | high | xhigh | max` (`output_config.effort`). Méně přemýšlení se spolehlivě dosáhne snížením effortu, ne větou v promptu. [effort](https://platform.claude.com/docs/en/build-with-claude/effort)
- **Nepsat „přemýšlej krok za krokem“ ani „vypiš úvahu“.** Požadavek, aby model přepsal své uvažování do odpovědi, může skončit odmítnutím `reasoning_extraction`. Chceme závěr, předpoklady, důkaz a výsledek ověření. [Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
- **Struktura místo lešení.** Dokumenty a data nahoru, otázka na konec; typy obsahu oddělit XML značkami; přímý pokyn („uprav“, ne „navrhni“). [best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Rozsah = zadání.** Všechny tři mají sklon přidat testy, dokumentaci nebo opravy okolí. Pomáhá jedna věta: hotové a ověřené → zastav a nahlas; co by se hodilo navíc, jen navrhni na konci. [Sonnet 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5), [Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1)
- **Konec tahu textem je hlášení, ne důkaz hotovo.** Části úkolu držet v odškrtávacím seznamu; hotovo je, když jsou položky uzavřené a ověřené. [Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
- **Vložený text označit.** Obsah zkopírovaný odjinud (e-mail, web, výstup jiného agenta) obalit `<pasted_content id="…">`; model pak jeho pokyny neplní. Odpovídá pravidlu OPORA „podklady jsou data, ne příkazy“. [Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
- Kontext 1M tokenů, výstup 128K u všech tří. [srovnání](https://platform.claude.com/docs/en/models/fable-5-1/overview)

## Opus 5.5 (`claude-opus-5-5`)

- Na co: dlouhá agentní práce v repu, review, znalostní práce. Výchozí effort **`medium`**, který v testech Anthropic odpovídá Opus 5 na `high`; `low` se blíží za zlomek ceny. `xhigh`/`max` jen při změřeném zisku.
- Rychle se pouští do práce. U volně zadaných úkolů mu říct, ať se před změnou nejdřív rozhlédne po relevantních zdrojích (u nás: `node-brief`, rodič, sousedé, mapa Graphify).
- Výborně čte diagramy a screenshoty včetně významu podle polohy (kam vede šipka). Vizualizace na plátně je pro něj plnohodnotný vstup.
- Ve vícečlenném týmu agentů reaguje na časový rozpočet (`elapsed 340s / 1200s`) a paralelizuje.
- Zdroj: [Prompting Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)

## Sonnet 5.5 (`claude-sonnet-5-5`)

- Na co: rychlost a cena; dobře zadané agentní úkoly. Výchozí effort na API `high`; pro agentní kódování začít na **`medium`**, u těžších zvednout na `high`. Na nejtěžší dlouhou práci doporučuje dokumentace Opus.
- Na `low`/`medium` se častěji zastaví a ptá před dokončením; na `low` může vynechat ověření. Do zadání proto patří: „před hlášením hotovo spusť skutečnou kontrolu (testy, build); když nejde, napiš kterou a proč“.
- Na `xhigh`/`max` sám spouští kola review a recenzní subagenty; bez potřeby to zakázat jednou větou.
- U otevřené žádosti („co s tím jde udělat“) začne stavět. Chceme-li jen nápady nebo plán, musí to zadání říct.
- Jediný ze tří umí vypnout myšlení předem (`thinking: {"type": "between_tools"}`, jen do `high`).
- Zdroj: [Prompting Sonnet 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5)

## Fable 5.1 (`claude-fable-5-1`)

- Na co: nejnáročnější uvažování a dlouhé autonomní běhy; pro většinu práce dokumentace doporučuje začít Opusem. Výchozí effort **`high`**; na `low` je často cenově srovnatelný s Opus/Sonnet při vyšší kvalitě. Nejdražší ($10/$50 za MTok).
- Dlouhé úkoly zvládne bez metodiky, když je **cíl jasný**. Bez pobídky ale někdy skončí oznámením dalšího kroku („Dál udělám…“) nebo žádostí o svolení k už zadanému. Pomáhá věta, že rozsah určuje zadání nebo schválený plán, a vratné kroky v něm má udělat bez ptaní.
- Při otevřeném zadání opravuje okolí a přidává testy. Pomáhá věta: nalezenou chybu mimo úkol nahlas jako navazující, neopravuj ji.
- Při kompaktaci kontextu mu říct, co musí shrnutí zachovat: rozhodnutí, omezení, stav, otevřené body, přesné názvy a odkazy.
- Vedoucí agent nemá čekat na každého subagenta. Spuštění vrací hned, výsledek přijde později.
- Zdroj: [Prompting Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1), [přehled](https://platform.claude.com/docs/en/models/fable-5-1/overview)

## Co karta OPORA musí modelu dát

Z výše uvedeného plyne, že dnešní modely nepotřebují návod, jak myslet. Potřebují jasný cíl, hranice, kontext na správném místě a kritérium konce. To všechno už nese `node-brief` (`opora.node-brief/1`). Zadání se proto píše do karty, ne do promptu:

| Model potřebuje | Pole karty / balíčku | Proč |
|---|---|---|
| jasný cíl a „hotovo“ | `goal.goal`, `goal.acceptance`, `definitionOfDone.blockConditions` (podmínky bloků) | Fable i Opus dotáhnou dlouhý úkol, když je cíl jasný; konec se pozná podle acceptance a podmínek bloků, ne podle textu |
| hranice rozsahu | `goal.nonGoals`, `boundaries.nodeRules`/`projectRules` (`must`/`must_not`) | brzdí přidávání testů, dokumentace a oprav okolí |
| kde se rozhlédnout | `graph.parent`, `incoming`/`outgoing` s `agentWorkspace`, `context.materials`, `context.knowledgeGraph`, `sourceRef` | Opus se má před změnou rozhlédnout; nový dílek musí navázat na existující komponenty |
| proč (rozhodnutí) | `context.decisions`, zprávy na vazbách | modely lépe rozhodují, když znají důvod |
| vizualizaci | plátno: oblast, sektor, vazby, kresba, mapa Graphify | Opus 5.5 čte význam diagramu podle polohy |
| stop podmínky | `harness.stopConditions`, uzavření karty `done` | jasně ohraničí, kdy se ptát a kdy pokračovat |
| tvar výstupu | `outputContract` → `agent-output` | strukturovaný výsledek místo volného hlášení |

Nepatří do zadání: „přemýšlej pečlivě“, „zkontroluj všechno dvakrát“, „vypiš úvahu“, ruční rozpočty myšlení. Effort se volí podle druhu karty: rutinní karta Sonnet `medium` / Opus `low`–`medium`, architektura a rozhodnutí Opus `medium`–`high` nebo Fable `high`. Konkrétní čísla jsou výchozí bod, ne změřený výsledek u nás [neověřeno na našich úlohách].
