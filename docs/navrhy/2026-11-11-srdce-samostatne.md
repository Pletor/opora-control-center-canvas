# Srdce samostatně: bez dotazů na člověka, vždy s vírou v cíl (11. 11. 2026)

Rozhodnutí vlastníka: „Srdce ať neposílá dotazy, úplně to zruš, nedokáži na to odpovídat. Ať funguje samostatně,
místo dotazů mu předej skill vira-modelu, se kterým musí vždy pracovat, ať to řeší samostatně a autonomně.“

## Co se ruší (celé, i s testy, CLI, dokumentací a UI)

- **Eskalace na člověka**: `gate.escalate`, `POST /api/brain/heart/escalate`, `GET /escalations`, `withdraw`,
  CLI `opora_heart.py escalate`, háček `heart_escalation_hook` → Pletor, sekce ESKALACE v podkladech Pletora,
  Pletorova fronta otázek (`/api/pletor/questions`), propis do Velína (`askedFor="human"`).
- **Výslech člověka**: `brief.ask` (`POST /api/brain/heart/ask`), režim `vyslech` (`MODE_SKILLS`, seed
  `skills/vyslech`), CLI `ask`, buzení srdce „odpověď člověka na výslech“. Rešerše a syntéza zadání srdcem zůstávají
  (srdce si podklady dohledá samo).
- Druh brány `ask` pro dělníky (dělník → srdce) zůstává; srdce odpovídá samo, `for: human` už nevzniká.
- Otevřené lístky `ask` s `for: human` v živých datech se jednorázově uzavřou jako odpověď srdce
  („Zrušeno: srdce rozhoduje samo podle víry v cíl.“), nic se nemaže.

## Co se přidává

- Skill **`vira-modelu`** je součást systémového promptu srdce vždy (jako `heart`): seed
  `backend/brain/seed/opora-heart/skills/vira-modelu/SKILL.md` (tělo z `.claude/skills/vira-modelu/SKILL.md`,
  odkazy na `references/` a `scripts/` přepsané na to, co srdce opravdu má), pin `opora:brain:skill:vira-modelu@…`
  v `brainPins` dávky.
- Prompt srdce (`skills/heart/SKILL.md`): místo „polož escalate / ask“ platí „rozhodni sám podle víry v cíl:
  podklad > domněnka, zapiš rozhodnutí a důvod do deníku karty / rozhodnutí, pokračuj“. Nová verze skillu se
  aktivuje v registru Brainu (stávající postup kandidát → aktivace).

## Hranice

- Bezpečnostní pravidla brány (role, tokeny, `autonomy.full`, nevratné zásahy) se nemění; co srdce nesmí, nesmí
  dál, jen se už neptá – rozhodne v mezích, nebo krok vynechá a zapíše proč.
- Člověk dál může srdci napsat (Pletor, zpráva srdci); jen srdce nečeká na odpověď.
