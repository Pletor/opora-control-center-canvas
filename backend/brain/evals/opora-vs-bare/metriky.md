# Metriky: v čem je OPORA lepší a v čem horší

Rozhodnutí uživatele 2026-10-28: stejné zadání pro A i B, jak si agent poradí, je na něm. Měříme kvalitu výstupu
**i** cenu práce, aby bylo vidět, jestli OPORA přidává kvalitu, nebo jen pálí tokeny.

## 1. Kvalita výstupu (obě ramena stejně, bez znalosti ramene)

| # | Metrika | Jak se měří | Rozsah |
|---|---|---|---|
| Q1 | **Funkčnost** | programové kontroly případu (build, test, routy, sekce v DOM, kritéria záměru, přechody cesty v prohlížeči) bez kritérií, která zadání nežádá | podíl 0–1 |
| Q2 | **Pokrytí záměru** | sekce a kritéria případu splněná staticky i za běhu | podíl 0–1 |
| Q3 | **Chybové a prázdné stavy** | případy se stavy (formulář, chyba serveru): každý stav vyvolaný v prohlížeči (Playwright) a viditelný | podíl 0–1 |
| Q4 | **Přístupnost** | bez nové závislosti, v prohlížeči: `lang`, právě jeden `h1`, pořadí nadpisů bez skoku, každý odkaz/tlačítko s přístupným jménem, `label` u polí, `alt` u obrázků, viditelný fokus | podíl 0–1 |
| Q5 | **Vzhled a pocit** | slepý párový soudce dostane **screenshoty** obou výstupů (desktop 1280 a mobil 390) + záměr; hodnotí, jak stránka působí vůči „Pocit“ a cíli | 1–5 |
| Q6 | **Věrnost textu záměru** | slepý soudce nad diffem a screenshoty: obsah sekcí odpovídá záměru (počty, pořadí, tón) | 1–5 |
| Q7 | **Kvalita kódu** | slepý soudce nad diffem: členění, čitelnost, mrtvý kód, testy, které něco ověřují | 1–5 |
| Q8 | **Testy** | počet testů agenta, které projdou, a zda testují kritéria záměru (počet `expect` na kritérium, soudce ano/ne) | počet + 0–1 |
| Q9 | **Celkový verdikt** | slepý soudce: lepší A / B / remíza / obě špatně | `pair_win` |

Pořadí obrazovek u soudce se losuje; soudce nikdy neví, které řešení je s OPOROU.

## 2. Cena práce (obě ramena)

| # | Metrika | Jak se měří |
|---|---|---|
| C1 | Čas agenta | `latency_s` |
| C2 | Tokeny a cena | `usage` (vstup, výstup, cache) a `reported_cost_usd` z CLI |
| C3 | Volání nástrojů | `tool_calls`, `turns` |
| C4 | **Zbytečné pokusy** | výsledky nástrojů s chybou (HTTP 4xx/5xx, Traceback, exit ≠ 0, `ok: false`) a opakování téhož příkazu; u A zvlášť chyby OPORY |
| C5 | Soubory mimo zadání | soubory v repu, které nejsou kód aplikace (pomocné skripty, `.md` poznámky, drafty) |

## 3. Práce s OPOROU (jen A – „jak agent musí pracovat s OPOROU, aby to nebyla jen zátěž“)

| # | Metrika | Jak se měří (čtení izolované OPORY po běhu, před jejím ukončením) |
|---|---|---|
| P1 | Plán | aplikace, stránky se `goal`/`feel`/`sections`, cesty; karty se `spec.steps`; počet kroků |
| P2 | Dotažení | podíl karet `done`; `mapGaps` po běhu; ověřené cesty (`lastRun` passed) |
| P3 | Plán ↔ kód | sekce z mapy, které jsou v kódu (`data-opora-section`), a naopak |
| P4 | Podíl režie | podíl volání nástrojů a času na OPORU vs. na kód; chyby OPORY (C4) |
| P5 | Kontext mimo OPORU | `.md`/poznámky v repu místo v OPOŘE (pravidlo „OPORA je mozek“) |

## 4. Souhrn

- **Kvalita** = průměr Q1–Q4 (0–1) a Q5–Q7 převedené na 0–1; **zisk OPORY** = kvalita A − kvalita B na stejném
  případu, průměr přes opakování.
- **Kvalita na cenu** = kvalita / minuty agenta a kvalita / USD.
- Tabulka „lepší / horší“: pro každou metriku Q a C, kde je A lepší, horší, nebo stejné (rozdíl < 0,05 nebo < 0,5 bodu).
- 2 opakování na rameno a případ: výsledky jsou orientační, ne statisticky průkazné; zpráva to říká.
