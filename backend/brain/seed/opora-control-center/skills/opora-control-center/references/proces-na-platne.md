# Proces na plátně: přehled

Kdy mě číst: potřebuješ jen přehled, jak se kreslí proces na plátno toku; podrobnosti jsou ve skillu srdce.

Plný postup kreslení procesu na plátno toku (kroky, nástroje `library nodes|case|brief`, případy a simulace, výrazy,
`custom.step`, příklad Uložit BMI) je skill srdce `proces-na-platne`: `python opora_heart.py skill proces-na-platne`
(zdroj `backend/brain/seed/opora-heart/skills/proces-na-platne/SKILL.md`). Zpráva člověka s `KONTEXT PLÁTNA` na něj
odkazuje. Kontrakt: `docs/navrhy/2026-11-04-platno-procesu.md` §1–§1b.

Stručně:
- Čti plátno (`library get FLOW`), z textu odvoď vrstvy `fe` / `be` / `db` / `infra`, kroky, data na hranách a větve.
- Typy z katalogu `GET /api/flow/node-types?kind=library_flow` (`use`, `avoid`, `intents`); `custom.step` jen tam, kde
  žádný typ nesedí.
- Kresli do draftu (`library nodes add|set|connect`), přidej případy (`library case add`, v pořádku + chybová větev) a pusť
  je (`library case run`), dokud `expect.ok` není pravda. Zadání pro agenta: `library brief FLOW`.
- Draft přijímá člověk na plátně; verzi neaktivuješ, cizí uzly nemažeš.
