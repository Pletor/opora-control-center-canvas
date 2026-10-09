# Záznam činnosti

Kontrakt: `docs/zaznam-cinnosti.md` (backend `GET /api/activity-log`).

Ikonka Záznam činnosti (`activity`) stojí v horní liště hned vlevo od Historie uložení a Uložit vše; App ji ukazuje za stejné podmínky (otevřené plátno). Panel pod ní má dvě záložky **Já** (actor=human) a **Agenti** (actor=agent) s počtem načtených zápisů a počtem selhání. Rozsah = aktuální projekt a pracovní prostor; přepínač „Jen vybraná karta“ přidá `nodeId` vybrané karty.

- `components/ActivityLogTools.tsx` – rodič dílků: otevřenost, záložka, filtr karty; čte záznam přes `use-activity-log` jen při otevřeném panelu. Od App dostane `project`, `workspace`, `nodes` (jména karet), `selectedNodeId`, `refreshKey` (otisk plátna + revize) a `onOpenNode`.
- `ActivityLogButton`, `ActivityLogPanel`, `ActivityLogTabs`, `ActivityLogList`, `ActivityLogRow` – jen props → JSX, změny hlásí callbackem.
- `logic/activity-log.ts` – čisté funkce: popisek akce z cesty (`actionLabel`), doplněk ze summary, selhání (ne-2xx), místní čas, dny (Dnes / Včera / datum), jména karet z grafu, dotaz, slévání stránek (`mergeFresh`, `appendOlder`), čísla záložek. Test vedle.
- `logic/use-activity-log.ts` – dvě stránkované řady (human, agent), „Načíst starší“ přes `nextBefore`; změna rozsahu načtené zahodí.
- `styles/activity-log.css` – blok `activity-log`; člověk = `--accent` + postava, agent = `--cat-agents` + robot (jako žeton práce v souhrnu agentů), selhání = `--danger`.
