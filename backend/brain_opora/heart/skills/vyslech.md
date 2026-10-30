# Výslech: pochopit, dohledat, vyslechnout, teprve pak plánovat

Čteš to, protože dávka má řádek `VÝSLECH`. Požadavek není dotaz k odpovězení, ale záměr k pochopení.
Karty k požadavku plánuješ až poté, co `brief` vrátí `status: clear`.

## Jak se na požadavek dívat
- Nejdřív účel a reálné použití: k čemu to člověk potřebuje, kdo to bude používat a v jaké situaci. Seznam až potom.
- Příklady člověka jsou vzorky záměru, ne hranice. U každého výčtu se zeptej: „čeho jsou to příklady?“ a doplň,
  co do té třídy patří a člověk to nenapsal.
- Hledej, co věc potřebuje, aby:
  - spolehlivě fungovala (chyby, limity, výpadky, data navíc);
  - byla pozorovatelná (jak člověk pozná, že běží a jestli dobře);
  - na ni mohly navázat další karty (rozhraní, uložená data, závislosti).
- Nenafukuj rozsah. Přidej jen to, co účel vyžaduje; nápad navíc patří do `outOfScope` nebo `assumptions`.
  O zadání se nepřetahuj.

## Postup
1. **Situace.** Spis máš zhuštěný v řádku `VÝSLECH`: větu člověka doslova, oblast, milník a karty se štítky.
   Víc dočti `ctx` nebo snímkem, jen když to syntéza potřebuje.
2. **Rešerše.** Jedna otázka: *co tahle věc potřebuje, aby spolehlivě fungovala a mohly na ni navázat další?*
   `python opora_heart.py research --requirement rq_… --question "…" --title "…" [--layer …]`
   Na požadavek je strop ceny. Když odpoví `brief_research_spent`, další rešerši nespouštěj a rozhodni z toho, co máš.
   Krátký výslech karty (`VÝSLECH (krátký)`) rešerši nepotřebuje.
3. **Syntéza.** Napiš JSON (Write) do `dilna/out/brief.json` a ulož ho:
   `python opora_heart.py brief --requirement rq_… --synthesis @dilna/out/brief.json`
   Odpověď vrátí `status` a `missing`. Doplň, co chybí, a ulož znovu.
4. **Výslech.** Otázky, které by změnily plán, polož člověku (nejvýš 3 najednou, nejvýš 3 kola):
   `python opora_heart.py ask --requirement rq_… --question "…" --recommended "…" --why "…"`
   Každá otázka má doporučenou odpověď a důvod, aby ji člověk mohl jen potvrdit. Ptej se po jedné věci,
   seřaď je podle dopadu na plán. Stojí-li syntéza na předpokladech (`assumptions`), zeptej se aspoň na ten
   nejdůležitější: bez jediné odpovědi člověka kód jasno nevydá. Když dojdou kola (`brief_rounds_spent`), rozhodni sám a nejasnosti zapiš
   do `assumptions`. Na odpověď člověka čekej do další dávky.
5. **Jasno → plán.** Až `brief` vrátí `clear`, naplánuj karty (`plan`). Každá má 2–8 kroků s `kind` a `files`.

## Tvar syntézy (jiné klíče kód odmítne)
```json
{"goal": "cíl jednou větou",
 "users": "pro koho",
 "parts": [{"text": "část nebo metrika", "origin": "human", "source": "věta člověka"},
           {"text": "…", "origin": "research", "source": "https://… z rešerše"},
           {"text": "…", "origin": "derived", "source": "z čeho to plyne"}],
 "acceptance": [{"text": "měřitelné kritérium", "check": "test"},
                {"text": "…", "check": "measure"},
                {"text": "…", "check": "observe"}],
 "outOfScope": ["co ne"],
 "assumptions": ["co předpokládáš"],
 "risks": ["co se může pokazit"],
 "dependencies": [{"ref": "nodeId|areaId", "text": "na čem to stojí"}],
 "questions": [{"text": "otevřená otázka", "impact": "high", "answer": "odpověď, když ji znáš"}]}
```
- `origin`: `human` (řekl člověk), `research` (zdroj z rešerše), `derived` (odvozeno; `source` = z čeho).
  `research` a `derived` musí mít `source`. Aspoň jedna část není `human`, jinak je to jen přepis zadání.
- `check`: `test` | `measure` | `observe`; kritérií aspoň 3, každé ověřitelné.
- `impact`: `high` | `medium` | `low`. Otázka `high` bez `answer` brání jasnu: polož ji přes `ask`,
  nebo ji rozhodni a odpověď zapiš do `answer`.
- Bez závislostí napiš `{"ref": "none", "text": "proč žádné"}`.

## Krátký výslech karty
`VÝSLECH (krátký): karta …` = kartě chybějí podklady. Doplň jí 2–8 kroků s `kind` a `files` příkazem `steps --node ID --file F` (ne `plan`), nic jiného.
