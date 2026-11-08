# Otázky Pletora Srdci a místo pro odpovědi

Stav: kontrakt, 8. 11. 2026. Navazuje na `2026-11-04-pletor-jarvis.md` a `docs/brain-heart.md` §3c–3d. V auditu
V8 rev. 3 jde o část B6-P (L15: ve frontě ≠ zodpovězeno) a B3 (L17: legitimní „nevím“ s důvodem).

## Proč

Pletor drží v hlavě celý plán, ale s člověkem řeší jednu věc (například jak má vypadat přihlášení). Fakta k ní
mu zjišťuje Srdce: výzkumem (`research`, `duel`), schránkou zadání a čtením kódu. To už Srdce umí. Chybí cesta
zpátky: Pletor dnes vidí jen 400 znaků souhrnu poslední dávky, bez vazby na svou otázku, a nemluví, dokud
nenapíše člověk.

## Pravidla

1. **Jedna otevřená otázka na projekt.** Dokud ji člověk neuzavře, Pletor novou neposílá, jen tu stávající
   upřesní. Upřesnění Srdce znovu vzbudí a otázka je zase „ve frontě“.
2. **Stavy:** `asked` (ve frontě Srdce) → `answered` (Srdce odpovědělo) → `closed` (uzavřel člověk). Upřesnění
   vrací `answered` → `asked`. Pletor stavy nezaměňuje: „poslal jsem“ není „Srdce zjistilo“.
3. **Odpověď Srdce** má text, odkazy (`refs`: ID fragmentu schránky, výzkumu, cesta k souboru) a smí být
   `unknown` s povinným `reason` (proč nevíme a co by to rozhodlo). Odpovědět může jen Srdce.
4. **Pletor si člověka sežene.** Když Srdce odpoví, Pletor dostane deterministickou zprávu (role `heart`) jen
   s ukazatelem: která otázka, čeho se týká a kde je výstup (sekce podkladů, odkazy, případné „nevím“).
   Pletor spustí vlastní tah a odpověď ještě neprezentuje, jen zjistí, jestli je člověk připravený a dává
   pozor. Tento tah nespouští akce.
5. **Výklad a konzultace.** Po souhlasu člověka Pletor najde výstup v podkladech a vyloží ho: co je doložené,
   co zůstává neznámé a co navrhuje. Pak s člověkem rozebere směry, jak problém vyřešit. Výsledkem je schválená
   varianta, nebo upřesnění otázky.
6. **Schválení uzavírá člověk.** Akce `heart_question_close` projde jen v tahu, který začal zprávou člověka.
   Znamená „tato varianta je v pořádku“ a vzbudí Srdce zprávou `SCHVÁLENO pq_…`. Srdce pak schválenou cestu
   rozpracuje na plátno a nic si nedomýšlí. Další otázka na to navazuje a posouvá projekt.
7. **Fakta, ne domněnky.** Srdce hledá v ověřitelných zdrojích: oficiální dokumentace, kód, spolehlivé weby
   a přepisy videí na YouTube. Citace ověřuje kód. Když nic nenajde, odpoví „nevím“ s důvodem.

## Data

`<data>/projects/<p>/brain/pletor_questions.json`, seznam otázek:

```
{id: "pq_…", workspace, text, status: "asked"|"answered"|"closed", askedAt,
 refinements: [{text, at}],
 answers: [{text, refs: [str], unknown: bool, reason?: str, at, by}],
 closedAt?, closedNote?}
```

Otevřená = `status != "closed"`. Zápis přes zámek souboru (vzor `agi_pletor/linie/jsonfile`).

## Cesta

| Krok | Kdo | Jak |
|---|---|---|
| Otázka | Pletor, akce `heart_question {text}` | Bez otevřené otázky založí `pq_…`, jinak přidá upřesnění. Vzbudí Srdce `Heart.message` textem `OTÁZKA PLETORA pq_…: <text>` nebo `UPŘESNĚNÍ OTÁZKY PLETORA pq_…: <text>`. Jen se zapnutou bránou. Výsledek akce: `Otázka pq_… je ve frontě srdce.` |
| Práce | Srdce | Podle promptu: výzkum, schránka, kód. Ve stejné dávce vždy zakončí `pletor-answer`. |
| Odpověď | Srdce, `python opora_heart.py pletor-answer --question pq_… --text T [--ref R]… [--unknown --reason R]` | `POST /api/pletor/questions/{id}/answer` jen pro agenta, tedy token Srdce. Stejný text podruhé se nezdvojí, na uzavřenou otázku 409. Uloží odpověď a zneplatní cache podkladů Pletora. |
| Oznámení | Pletor | Na pozadí: do rozhovoru zapíše zprávu role `heart` s ukazatelem a spustí tah „zjisti, jestli je člověk připravený“. Odpověď Pletora se uloží jako běžná zpráva `pletor`. |
| Výklad | Pletor v dalším tahu člověka | Odpověď vezme ze sekce podkladů a vyloží ji, pak konzultace směrů. |
| Schválení | člověk přes Pletora, akce `heart_question_close {text}` | Jen v tahu zahájeném člověkem. Uzavře otázku a vzbudí Srdce zprávou `SCHVÁLENO pq_…: <text>` s původní otázkou a zkrácenou odpovědí. Srdce pak práci rozpracuje na plátno. |

Podklady Pletora dostanou sekci **OTÁZKA PRO SRDCE**: otevřená otázka s upřesněními, stavem a poslední
odpovědí (text, refs, unknown/reason) a jedním řádkem poslední tři uzavřené. Strop sekce se vezme z ostatních
sekcí, `LIMIT` 6000 zůstává.

Čtení: `GET /api/pletor/questions?project=` (člověk) pro panel.

## Prompt

- Srdce (seed `backend/brain/seed/opora-heart/skills/heart/SKILL.md` a verze skillu v Brainu): řádek nástroje
  `pletor-answer` a krátká část „Otázky Pletora“. Mění se jen tato jedna věc (lekce m11).
- Pletor (`persona.md`): akce `heart_question` a `heart_question_close`, pravidlo jedné otevřené otázky a tvar
  výkladu odpovědi.

## Hotovo, když

- Testy: dvě akce, pravidlo jedné otázky a upřesnění, route odpovědi (agent ano, člověk 403, uzavřená 409,
  `unknown` bez `reason` 422, opakování se nezdvojí), sekce podkladů se vejde do `LIMIT`, příkaz `pletor-answer`
  v nástroji Srdce, proaktivní tah bez akcí.
- Panel Pletora ukáže zprávu Srdce a následný výklad Pletora bez toho, že by člověk něco psal (poll stavu).
- `uv run pytest` (cíleně), `npm test`, `npm run build` zelené.
- Živě: otázka → dávka Srdce → `pletor-answer` → Pletor promluví.

## Výzkum z YouTube (součást M1)

Výzkumný stůl Srdce (`research_desk`) umí přečíst přepis videa přes `yt-dlp` (ruční titulky, jinak
automatické; cs, en). Citaci z videa ověřuje stejně jako citaci ze stránky. Video bez dostupného přepisu
se jako doklad nepoužije. Pořadí spolehlivosti zdrojů se nemění: oficiální dokumentace a specifikace jsou
před videem.

## Mimo M1

- **M2, průběhová paměť Pletora:** mapa celého plánu, aktivní téma a vedlejší věci, na které se v rozhovoru
  narazí. Ukládají se mimo aktivní otázku a jsou čitelné v podkladech. Dnes jen `vault_note` → `pletor_decisions.jsonl`. Staví se po schválení M1.
- Pletor neodpovídá na otázky Srdce za člověka, protože člověk má vlastní cestu `escalations`.
- Pletor nečte celé fragmenty schránky (cílené dočtení B6-P).
- Hlasové přečtení proaktivního výkladu.

## M1c: jeden rozhovor (rozhodnutí člověka 8. 11.)

Člověk nesmí přeskakovat mezi Pletorem a kartami „Čeká na vás“ v panelu Srdce. Všechno, co Srdce chce od člověka
nebo co mu odpovídá, jde přes rozhovor s Pletorem.

1. **Deník v rozhovoru.** Do rozhovoru se deterministicky zapíšou řádky role `heart` (vidí je člověk ve Velínu
   i Pletor v historii):
   - „Pletor se ptá srdce pq_…: <text>“ při položení otázky a „Upřesnění pq_…: …“ při upřesnění;
   - „Srdce odpovědělo na pq_… · uloženo: otázky Pletora (pq_…)[; odkazy …]“ (už existuje jako oznámení);
   - „Srdce se ptá člověka gt_…: <začátek textu> · uloženo: eskalace gt_…“ při každé nové eskalaci Srdce.
   Řádek nese ID a místo uložení, aby si ho Pletor mohl dohledat.
2. **Notifikace pro Pletora.** Nová eskalace Srdce spustí stejný proaktivní tah jako odpověď: Pletor řekne, čeho
   se týká, a zjistí, jestli je člověk připravený. Pak ji s ním probere v rozhovoru.
3. **Odpověď na eskalaci přes Pletora.** Akce `heart_escalation_answer {ticketId, text}` projde jen v tahu, který
   začal člověk, a jde stejnou cestou jako odpověď člověka v panelu (vzbudí Srdce). Původcem je člověk, Pletor jen
   předává jeho slova.
4. **Podklady.** Sekce eskalací ukáže celý text nejstarší otevřené eskalace (ostatní zkráceně), aby Pletor nemusel
   nic domýšlet.

Později se to nahradí novým tokem dat mezi Pletorem a Srdcem. Panel „Čeká na vás“ zatím zůstává, jen už není nutný.
