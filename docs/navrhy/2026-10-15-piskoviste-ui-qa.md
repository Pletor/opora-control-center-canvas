# QA přepínače disciplín Schránky (read-only, 2026-10-15, relace pískoviště d2aad1c0)

Zadání HERMES-P-QA-1503: nezávisle prověřit tok přepínače Kreslení · Logika · Provoz a „Čeká na tebe“
(`frontend/editor/brief-vault-dock/components/DisciplineSwitch.tsx`, `logic/discipline-groups.ts`, napojení v
`BriefVaultDock.tsx`) proti poslednímu zadání člověka: vždy jen zvolená skupina, přesné počty a odznaky, proklik
otevírá konkrétní čekající položky, po přepnutí se neukáže jiný workspace ani uzel. Bez zápisu do kódu, do Duelu, na 8745
ani do živých dat; jediný zápis je tento dokument.

## Vlastní procesy

- Dvě nečinné shelly mé relace z 12:27 a 12:30 (PID 9928/27004, 36360/25688; snapshot `j45zsl`, jen `conhost`) –
  pozůstatek subagentů autorů kontrol. Ukončení `Stop-Process` **zamítl klasifikátor oprávnění** (Interfere With Workloads);
  nechávám je, nic nedělají. Cizí procesy (backend 8740, 8745, Duel relace A) jsem se nedotkl.
- Zpráva relaci A („jen read-only QA, Duelu se nedotýkám“) – odeslání `SendMessage` **zamítl klasifikátor**; A to ví z mé
  předchozí zprávy (13:59) a z vlastní odpovědi (14:20), kde moje soubory převzala.

## 1. Zdrojová revize (očekávání → skutečnost v kódu)

| Požadavek | Kde | Výsledek |
|---|---|---|
| vždy jen zvolená skupina | `DisciplineSwitch.tsx`: `isOpen = activeGroup(view, live) === group.id`; pilulky `items.map(chip)` jen při `isOpen` | splněno; `Nezařazené` neotvírá žádnou skupinu (`activeGroup` → `null`) |
| hlavička = záložka | `<button aria-expanded>`; klik → `onView(target)`; otevřená skupina → `onView(view)` (no-op); spící → `disabled` | splněno |
| přesné počty | pilulka: `counts[id]` = `disciplineCounts(all)` (živé `brief` podle `effectiveDiscipline` v rozsahu, stejné jako dřív); hlavička: počet zapnutých neuronů, ne fragmentů | splněno; **poznámka**: hlavička ukazuje počet disciplín (např. „Logika 9“), ne fragmentů – záměr, ale člověk to může číst jako počet zadání |
| odznaky „čeká na tebe“ | `waitingByDiscipline(all, live, feedback)` = `waitingOnHuman(filterByDiscipline(all, id))` na disciplínu + Nezařazené; odznak na pilulce i součet na hlavičce (`groupWaiting`) | shodné s počtem řádků v Přehledu téže disciplíny (stejná funkce); viz nález N1 |
| proklik | pilulka „Čeká na tebe N“ → `onWaiting(next)` → dock: `setView(next); setSection("overview")` → Přehled vykreslí seznam „Čeká na tebe“ (řádky s akcí Otevřít / Odpovědět / Potvrdit / Ukázat) | otevře **seznam** čekajících položek disciplíny, ne přímo první položku – viz nález N2 |
| žádný jiný workspace/uzel | `setView` mění jen filtr disciplíny (localStorage `opora:vault-discipline:v1`), `vaultScope`, `project`, `workspace` ani `focus` se nemění; `onOpenNode` se nevolá | **jen zdrojové čtení** – za běhu v prohlížeči neověřeno (BLOCKED níže) |
| cyklus prokliku | `nextWaiting`: pořadí tabulky §2, dokola, Nezařazené na konci; bez čekajících → pilulka se nevykreslí | splněno (test) |

## 2. Cílené testy (existující)

```
npx vitest run frontend/editor/brief-vault-dock/components/BriefVaultDock.test.ts \
  frontend/editor/brief-vault-dock/logic/discipline-groups.test.ts \
  frontend/editor/brief-vault-dock/logic/disciplines.test.ts
→ Test Files 3 passed (3), exit 0
```
Pokrývají: jen otevřená skupina má pilulky, hlavičky `aria-expanded`, spící „spí“ + `disabled`, odznak na hlavičce
a pilulka „Čeká na tebe“ s celkovým počtem, `groupTarget` (čekající → obsah → první), `nextWaiting` dokola,
`waitingByDiscipline` nad stromem zúženým jako pohled.

## 3. Sondy nad živými daty pískoviště (jen GET)

- **Prohlížeč – BLOCKED.** Rozšíření Claude pro Chrome: „Browser extension is not connected“. Chrome DevTools MCP:
  „The browser is already running for …\chrome-profile“ (profil drží jiná relace – kolize sdíleného prohlížeče, A nesmím
  restartovat). Snímky obrazovky tedy nejsou.
- **Render bez DOM – BLOCKED (2 pokusy).** `npx vite-node <scratchpad>/probe-switch.ts` → `Cannot find module '/@fs/…'`
  (vite `fs.allow` nepustí soubor mimo kořen repa), exit 1; `npx vite-node --config <scratchpad>/vite.probe.config.ts …` →
  `Cannot find module 'vite'` (config mimo `node_modules`), exit 1. Sonda do repa nepatří (jediný povolený zápis je tento
  dokument), proto nepokračuji.
- **Čísla z API (Python, read-only, stejná pravidla jako `disciplineCounts` / `waitingOnHuman`):** 63 kořenů, všech 17
  disciplín zapnutých. Pilulky: ai 5, api 5, be 4, cache 4, cloud 5, content 5, cx 5, data 4, db 4, devops 5, fe 6,
  infra 4, observability 4, security 4, test 6, ui 5, ux 5. Odznaky: **každá disciplína 2 (infra 3), celkem 35**, všechny
  z položky „Výzkum „…“ čeká na tvou zpětnou vazbu“.

## Nálezy

**N1 (střední, zdrojové čtení + čísla z API) – odznaky „čeká na tebe“ počítají i výzkum pod uzavřenými cykly.** Reprodukce: otevřít Schránku pískoviště → každá
hlavička i pilulka má odznak 2–3, pilulka „Čeká na tebe 35“. Očekávání: čeká to, co má člověk rozhodnout. Skutečnost:
`waitingOnHuman` počítá každý `research` se `status: done` bez lidské zpětné vazby – tady výzkum z 1. běhu a „Doklady z
repa“ u kořenů, jejichž cyklus už skončil (`gates.learned: true`, agentní smyčka §11 lidskou zpětnou vazbu nepředpokládá).
Přepínač číslo jen věrně zrcadlí Přehled, ale pro člověka je to šum: nerozliší disciplínu, kde opravdu něco čeká.
Kód tak počítá záměrně podle dnešního pravidla modelu (hotový výzkum bez zpětné vazby, bez ohledu na `learned`); vyloučit
agentní výzkum nebo kořeny s uzavřeným cyklem je **návrh změny politiky**, ne automaticky povolená oprava – rozhodne člověk
nebo vlastník modelu (A). Možná podoba (ve `logic/vault-dock-model.ts`, neměněno): v `waitingOnHuman` nepočítat výzkum pod
kořenem s `learned` zapnutým, nebo samostatný tón „k přečtení“ místo „čeká na tebe“. Test: `vault-dock-model.test.ts` – kořen s `learned: true` a hotovým výzkumem bez zpětné vazby → 0
položek.

**N2 (návrh, ne vada) – proklik vede na seznam, ne na položku.** „Čeká na tebe“ přepne disciplínu a otevře Přehled, kde člověk
klikne na konkrétní řádek (Otevřít / Odpovědět …). Zadání „prokliknout věci, které se týkají mě“ je splněno na dvě kliknutí.
Nejmenší zlepšení (jen `DisciplineSwitch` + dock): při jediné čekající položce rovnou `onSection(item.section)`; při více
nechat Přehled. Není defekt proti kontraktu ani proti zadání; jde o možné zkrácení toku.

**N3 (návrh, ne vada) – počet na hlavičce.** „Logika 9“ je počet zapnutých neuronů, pilulky nesou počty fragmentů. Dvě různá čísla
vedle sebe bez popisku; `title` hlavičky to neříká. Nejmenší oprava: `title` doplnit „9 disciplín, 41 zadání, 18 čeká“,
nebo na hlavičce ukazovat součet fragmentů skupiny.

Izolace workspace/uzlu po přepnutí plyne jen ze čtení zdroje (`setView` nesahá na rozsah ani fokus), runtime důkaz
(prohlížeč) chybí. Shoda počtů je doložena cílenými testy (statický render) a čísly z API, ne snímkem běžící aplikace.

## Závěr

- **hotovo (zdrojové čtení + statické testy):** revize kódu a 3 cílené testovací soubory (exit 0); čísla z API dokládají,
  jaká data přepínač dostane. **Runtime důkaz z prohlížeče není** – izolace workspace/uzlu i vzhled jsou ověřeny jen čtením zdroje.
- **nález:** N1 – odznaky zahrnují výzkum pod uzavřenými cykly (chování podle dnešního pravidla modelu; změna = rozhodnutí o
  politice, vlastník `vault-dock-model.ts` je A). N2 a N3 jsou návrhy zlepšení, ne prokázané vady.
- **BLOCKED:** prohlížeč (rozšíření nepřipojené, DevTools profil drží jiná relace) a render nad živými daty mimo repo
  (vite `fs.allow`, 2 pokusy); ukončení vlastních nečinných shellů a zpráva relaci A zamítnuté klasifikátorem oprávnění.
