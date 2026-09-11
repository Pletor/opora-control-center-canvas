# Instalace a načítání

Tato složka je hotový projektový skill pro **Claude Code**, nikoli plugin aplikace.
Nemění databázi OPORA, model, oprávnění ani automaticky nespouští agenty.

## Kam složku dát

Doporučené projektové umístění:

```text
<repo>/.claude/skills/opora-control-center/SKILL.md
```

Pro použití ve všech projektech ji můžeš sám zkopírovat do
`~/.claude/skills/opora-control-center/`. Nekopíruj současně různé verze do obou
umístění. ZIP rozbal tak, aby nevzniklo dvojité `opora-control-center/` vnoření.

## Jak skill načíst

- Spusť Claude Code v projektu s touto `.claude/skills/` složkou.
- Automaticky: popiš činnost, například „V OPORA vytvoř uzel pod sektorem“.
  Claude rozhoduje podle `description`; text referencí nemusí předem načíst.
- Výslovně: `/opora-control-center` a následně konkrétní požadavek.
- Není-li rozpoznán, otevři novou relaci a ověř správnou cestu a název.
- Jiný klient než Claude Code může vyžadovat vlastní mechanismus importu skillů;
  existence složky sama o sobě nezaručuje podporu.

Není potřeba další „loader skill“ ani import celého manuálu do CLAUDE.md.
`SKILL.md` už obsahuje spouštěcí podmínky i rozcestník pro jednotlivé situace.

## Metadata a oprávnění

`name` odpovídá složce; `description` říká co a kdy použít. `model` není záměrně
nastaven — skill nemění tvůj aktuální model. `allowed-tools: Read, Grep, Glob`
předem nepovoluje obecný shell ani zápisy. **Samotné allowed-tools nelze chápat
jako zákaz všech ostatních nástrojů.** Skutečné zákazy patří do oprávnění klienta.

## Co je uvnitř

- `SKILL.md`: krátký aktivní postup a podmíněné načítání.
- `references/`: pracovní postupy, API, hranice a dohledatelné zdroje.
- `scripts/opora_read.py`: čtecí diagnostika; Python 3, bez dalších balíčků.
- `assets/task-brief.md`: šablona zadání; načíst jen při sestavování úkolu.

## Příklady zadání

- „Načti skill OPORA a zjisti dostupné projekty. Nic neměň.“
- „V projektu X vytvoř v sektoru Y koncept Z, bez souboru.“
- „Z uloženého zadání připrav podklady, ale model nespouštěj.“
- „U běhu ID ukaž skutečný výsledek a ověření; nic nerestartuj.“
- „Tlačítko nefunguje: minimální oprava bez testů, main a localhost.“

Příkazy a API byly odvozeny ze zdrojů aplikace; živé schopnosti vždy ověř znovu.
Podrobnosti a omezení viz `references/source-map.md`.
