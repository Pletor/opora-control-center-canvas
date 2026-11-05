# Dílna skillů

Stav: návrh ke schválení (2026-11-05). Navazuje na Brain (`backend/brain/README.md`, kontrakt `2026-11-03-novy-zaklad.md` §3.4), Pletora (`2026-11-04-pletor-jarvis.md`), nastavení Pletora a LLM (`2026-11-04-pletor-nastaveni-llm.md`) a budovatele záměru (`2026-11-05-budovatel-zameru.md`).

## 1. Proč

Skill, který spouští nástroje (restart serveru, nasazení po sloučení, cílené testy), je dnes ruční práce: složka se `SKILL.md`, skript, žádný test a žádná kontrola. Člověk nevidí, co skill smí, a ztrácí se verze. OPORA má na to už skoro vše: **Brain** (git úložiště, registr verzí, kandidát → eval → aktivace, návrat) i generování skillů do lokálních relací. Chybí **místo pro stavbu a editor**.

Dílna je samostatná část nastavení Pletora a srdce. Člověk tu řekne, co má skill dělat. Pletor ho přes doptávání (budovatel záměru) předá srdci, srdce postaví skill **i s Python skripty a jejich testy** jako kandidáta v Brainu. Člověk ho v editoru projde, vyzkouší a sám aktivuje.

## 2. Co už existuje

- `backend/brain/store.py`: git `<data>/brain/`, plugin = `plugins/<plugin>/skills/<skill>/SKILL.md` + volitelně `scripts/`, `evals/`.
- `backend/brain/registry.py`: artefakty a verze (`candidate` → `active`), `rollback`, piny.
- `backend/brain/evaluate.py` a `/api/brain-registry/*`: kandidát (`POST …/candidates`), eval, aktivace jen člověkem (`…/activate`, `force`), návrat.
- `backend/brain/local_skills.py`: aktivní verze se při startu vyexportuje do `.claude/skills/` pro lokální relace. Dnes jen `opora-control-center` (konstanta `SKILLS`).
- Skripty skillu s testy už jsou v seedu `opora-control-center` (`scripts/`, `uv run pytest backend/brain/seed/opora-control-center`).
- Nastavení Pletora: ozubené kolo, záložky Mozek a čtení / Hlas / LLM (`frontend/pletor/components/PletorSettingsPanel.tsx`).
- Frontend nemá knihovnu kódového editoru (CodeMirror, Monaco).

## 2a. Rozhodnutí člověka (2026-11-05)

- **Místo v kódu:** `backend/agi_pletor/pletor_opora_settings/` (skilly v `skills/`, funkce v `tools/`). Složku `agi_pletor` zakládá souběžné přejmenování modulu Pletora; Dílna na ně nezávisí a do cizích souborů nesahá.
- **Dvě okna editoru vedle sebe:** (1) editor skillu (postup `skill-creator`: záměr, `SKILL.md`, zkušební zadání, hodnocení), (2) editor funkcí, tedy Python skriptů `<nazev-funkce>.py`.
- **Funkce je deterministická a měřitelná.** Stejný vstup dá vždy stejný výstup a funkce nese vlastní měření (viz §3a). Co jde převést na funkci, nemá zůstat v textu skillu.
- **Pletor může do Dílny posílat procesy:** opakující se věci (tři stejné ruční kroky = kandidát na funkci) i spuštění pipeline při tvorbě (napsat → otestovat → změřit).

## 3. Model

- **Skill dílny** = artefakt Brainu v pluginu `opora-dilna` (jeden plugin pro skilly stavěné člověkem; seed `opora-control-center`, `opora-heart` a `ponytail` se nemění). Soubory: `SKILL.md`, `scripts/*.py`, `tests/test_*.py`, `manifest.json`.
- **Manifest oprávnění** (`manifest.json`): co skill smí. `commands` (spouštěné programy), `paths` (kam smí zapisovat), `network` (hostitelé), `destructive` (ano/ne). Dílna manifest ukáže před aktivací a skript, který zkouší víc, než manifest deklaruje, test odmítne.
- **Životní cyklus verze:** `draft` (rozpracované v editoru) → `candidate` (commit v Brainu) → testy skriptů → volitelný eval → **aktivace člověkem** → export do lokálních relací. Návrat je jedním krokem (`rollback`).
- **Export:** aktivní skilly pluginu `opora-dilna` se generují do `.claude/skills/` stejně jako `opora-control-center` (rozšíření `local_skills.SKILLS` o výčet z registru). Generovaná složka se nepřepisuje ručně; úprava se dělá jen v dílně.

## 3a. Funkce (`tools/<nazev-funkce>.py`)

- **Tvar:** modul s `def run(vstup: dict) -> dict`. Čistá funkce: bez náhodnosti, času a sítě v běhu, vše potřebné je ve vstupu. Co je nevratné nebo sahá do systému, patří do skriptu skillu s manifestem (§3), ne do funkce.
- **Měření:** vedle funkce leží `<nazev-funkce>.cases.json` s případy `{name, input, expected}`. Dílna je spustí, porovná výstup s očekávaným a vrátí `{passed, total, failed: [{name, got, expected}], durationMs}`. Změna funkce je lepší jen když `passed` neklesne.
- **Determinismus se ověřuje:** každý případ se spustí dvakrát a oba výstupy musí být shodné, jinak je funkce označená `nondeterministic`.
- **Spouštění v odděleném procesu** s časovým limitem a omezeným prostředím (bez sítě a mimo data OPORY), výstup zkrácený.
- **Skill funkci volá** přes skript (`python -m …`), takže skill dostane strojově čitelný výsledek místo prózy.

## 4. Stavba skillu

1. Člověk řekne Pletorovi, co má skill dělat („po sloučení PR nasaď server a ověř, že odpovídá“).
2. Pletor se doptá podle budovatele záměru: jaké příkazy, kde se pouštějí, co je nevratné, jak se pozná úspěch. Zeptá se jen na to, co nezjistí z repozitáře (např. porty, příkazy `uv`, `npm`).
3. Pletor zadá srdci (`heart_message`). Srdce vytvoří kandidáta: `SKILL.md` (kdy a jak skill použít, s důrazem na `description`), skripty `scripts/*.py` pro vše deterministické, testy, `manifest.json`.
4. Srdce dá Pletorovi vědět; Pletor shrne, co skill smí a co dělá, a otevře dílnu na kandidátovi.
5. Člověk skill projde, spustí testy, upraví a **aktivuje sám**. Srdce skill nikdy neaktivuje.

Pravidlo pro skripty: co jde deterministicky (restart, build, testy), patří do Pythonu, `SKILL.md` jen říká „spusť skript a ověř výstup“. Skript vrací strojově čitelný výsledek (JSON na stdout) a nenulový kód při selhání. Nevratné kroky (smazání, push, nasazení) skript dělá jen s přepínačem `--yes` a skill je ve `SKILL.md` označí.

## 5. Editor a rozhraní

- **Místo:** nová záložka **Dílna** v nastavení Pletora (ozubené kolo), ne samostatná obrazovka. Odkaz z velínu, až ten bude.
- **Rozvržení:** vlevo seznam skillů a strom souborů vybraného skillu, uprostřed editor, vpravo panel Oprávnění / Testy / Verze.
- **Editor (D2):** textové pole s monospace písmem, čísla řádků, hlídání nepřipraveného zápisu. Knihovna kódového editoru (CodeMirror) se přidá až po schválení jako samostatné rozhodnutí o závislosti.
- **Akce:** Uložit jako kandidáta, Spustit testy, Porovnat s aktivní verzí (diff), Aktivovat, Vrátit.
- Podle pravidel repozitáře: dílky ve `frontend/pletor/` (nebo `frontend/pletor-workshop/`), BEM CSS s příběhem, logika bez Reactu s testy.

## 6. Bezpečnost

- **Testy skriptů běží v odděleném adresáři** (kopie skillu v dočasné složce), s časovým limitem, bez sítě mimo manifest a bez přístupu k datům OPORY. Výstup se zkracuje.
- **Skript nepouští nikdo mimo člověka a explicitní skill.** Dílna nespouští skripty sama kromě testů.
- **Aktivace jen člověkem** (Brain to už vynucuje), eval je volitelný.
- Skripty a manifest jsou **data v git historii Brainu**: lze je vrátit, srovnat a dohledat autora (srdce / člověk).
- Žádné klíče ve skillech; skript čte klíče jen z prostředí, které skill výslovně deklaruje.

## 7. Milníky

Stavět se bude po jednom, po každém stop a schválení.

| | Co | Hotovo, když |
|---|---|---|
| **D0** | Funkce: načtení `tools/*.py` + `*.cases.json`, spuštění v odděleném procesu, měření (`passed/total`), kontrola determinismu | Dílna vrátí měřitelný výsledek funkce; nedeterministická je označená |
| **D1** | Čtení: seznam skillů pluginu `opora-dilna`, soubory a verze přes API, záložka Dílna jen ke čtení | V nastavení vidím skilly, jejich soubory a verze |
| **D2** | Editor a zápis kandidáta: úprava souborů, uložení jako kandidát, diff proti aktivní verzi, kontrola `SKILL.md` (název, popis) | Upravím skript, uložím kandidáta a vidím rozdíl |
| **D3** | Testy skriptů v odděleném adresáři + manifest oprávnění a jeho kontrola | Tlačítko Spustit testy vrátí výsledek; skript mimo manifest je odmítnut |
| **D4** | Aktivace a export do `.claude/skills/` (rozšíření `local_skills`), návrat verze | Aktivovaný skill je vidět v lokální relaci Claude Code |
| **D5** | Stavba rozhovorem: Pletor → srdce → kandidát (skill, skripty, testy, manifest) | Z věty „po sloučení nasaď server“ vznikne kandidát k posouzení |
| **D6** | Základní sada: restart serveru, nasazení po sloučení PR, cílené testy | Tři skilly postavené dílnou a aktivované člověkem |

## 8. Otevřené otázky

- **Jeden plugin `opora-dilna`, nebo plugin na skill?** Návrh: jeden, dokud nebude potřeba sdílet skill mimo OPORU.
- **Skill pro všechny projekty, nebo jen pro OPORU?** Návrh: nejdřív jen pro OPORU; globální (`~/.claude/skills`) až po D4.
- **Kódový editor:** textové pole stačí pro první verzi; CodeMirror je nová závislost k odsouhlasení.
- **Kolidující práce v nastavení:** jiná relace právě staví stránku nastavení (`frontend/settings/`) a přejmenovává modul Pletora. Dílna se napojí až po jejich sloučení (viz závislost níže).

## 9. Závislosti a pořadí

D1 a D2 nepotřebují budovatele záměru. D5 ano (B1 a B2 z `2026-11-05-budovatel-zameru.md`). Do té doby jde skill vytvořit a upravit ručně v editoru, což je užitečné samo o sobě.
