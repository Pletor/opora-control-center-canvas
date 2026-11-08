# Linie: zkouška v živém náhledu a squash přijetí

Stav: kontrakt, 8. 11. 2026, rozhodnutí člověka. Navazuje na `2026-11-06-velin-git-linie.md` a `2026-11-06-linie-rebrand.md`.

## Proč

Při vývoji komponenty vzniká na větvi mnoho commitů: oprava po každé zkoušce. Člověk musí zkoušet přesně aktuální
verzi na živé URL a přijímat to, co vyzkoušel. Rodič má dostat jeden čistý commit na úkol, ne hromadu oprav.

## Pravidla

1. **Větev = pracovní stůl.** Commity na větvi jsou body návratu. V Linii zůstávají vidět jako kostky.
2. **Squash přijetí pro `feat/*` a `fix/*`.** Začlenění do rodiče je jeden commit (`git merge --squash` + commit).
   - Zpráva: první řádek je titulek kuličky, pak essence, pak výpis commitů větve (`base..head`, jeden řádek na commit)
     a trailer `Opora-Mark: <mark>`.
   - Merge log nese `mode: "squash"`, `source_sha` (hlava větve) a `result_sha` (squash commit).
   - Začlenění a uzavření větve se po squashi poznají podle merge logu (`finished.ok`) nebo podle commitu v cíli
     s trailerem `Opora-Mark` téže kuličky, ne podle předků. `work.unreported` po squashi nesmí vrátit celou větev.
   - Při selhání se worktree vrátí do původního stavu (`reset --hard`), ne `merge --abort`.
   - Ostatní typy řádků (`develop`, `main`) slučují dál merge commitem.
3. **Náhled se drží hlavy.** Když kulička už náhled má a nový report (routa i brána přes `ticket.py`) posune hlavu,
   náhled se sám restartuje na novou hlavu.
   - Spouští ho služba jako agent. První spuštění náhledu zůstává akcí člověka.
   - Tlačítko se jmenuje **Vyzkoušet**: bez náhledu ho spustí, s náhledem otevře URL.
4. **Stav náhledu v kuličce.** `work.preview = {slug, sha, url, state: building|running|failed, at}`. UI ukáže
   „běží na `abc1234` · aktuální“, „staví se na `abc1234`“, „zastaralý, hlava je `def5678`“ nebo „selhal, log“.
   URL je v detailu (záložka Git i Souhrn) a v řádku „Čeká na tebe“.
5. **Data náhledu přežijí restart.** Kopie ostrých dat vznikne jen při prvním startu. Restart data drží.
   - Akce **Obnovit data z ostrých** (jen člověk) udělá čerstvou kopii.
   - `remove` dál maže všechno.
6. **Zkouška má evidenci.** Kliknutí člověka na Vyzkoušet (otevření běžícího náhledu) zapíše
   `work.tried = {sha, at}` a do deníku `linie.preview.tried`.
7. **Přijetí = vyzkoušené SHA.**
   - `acceptance.tested` = SHA, na kterém člověk naposledy zkoušel.
   - Fronta „Čeká na tebe“ ukáže „vyzkoušeno na A“, nebo „nevyzkoušeno“.
   - Když `tried.sha ≠ hlava`, ukáže „vyzkoušeno na A, hlava je B“ a přijetí nabídne až po nové zkoušce. Přijmout
     nevyzkoušené jde jen výslovně („přijmout bez zkoušky“).
8. **Co je nového od poslední zkoušky.** Detail i řádek fronty ukáže commity `tried.sha..hlava`, nejvýš 10 a pak
   „+N“.

## Hotovo, když

- Testy: squash merge (zpráva, trailer, log, uzavření, `unreported` prázdné po squashi, selhání vrátí worktree),
  restart náhledu po reportu jen s existujícím náhledem a jen při nové hlavě (routa i brána), data přežijí
  restart a obnova je čerstvá, `tried` a `tested`, fronta a přijetí podle zkoušky, seznam novinek.
- Frontend: Vyzkoušet, stav náhledu, URL, novinky, obnova dat; logika v `logic/*.ts` s testy.
- Cílené pytesty Linie, `npm test` a `npm run build` jsou zelené. Živá ukázka: report → náhled se sám přestaví →
  Vyzkoušet → přijetí → squash do rodiče.

## Doplněk: odkaz přímo na změnu a návod (8. 11., člověk)

Člověk nechce skládat URL ani hledat, kde se změna projevuje.

- `linie.py report` přijme `--try "<query>"` (místo v aplikaci, např. `screen=pletor&environment=editor&part=linie`)
  a opakované `--step "<krok>"` (co udělat a co má být vidět). Uloží se do `work.tryout = {at, steps, sha}`.
  Report bez `--try` převezme předchozí `tryout`.
- `trial.url` = URL náhledu + `project` + `workspace` + `tryout.at`. Tlačítko Vyzkoušet otevírá vždy tento odkaz.
- Detail (Souhrn) i řádek „Čeká na tebe“ ukážou **Jak vyzkoušet**: očíslované kroky z `tryout.steps`.
- Skill git-linie a `CLAUDE.md` (sekce Práce na úkolu Linie): report nese `--try` a `--step`.
