# Velín řídí postupný vývoj přes Git větve, náhledy a přijetí

Stav: kontrakt M1 (2026-11-06). Zadání: člověk chce rozpracovávat jedno téma do hloubky, vidět skutečné UI
před sloučením a průběžně korigovat; přijetí konkrétního výsledku předchází postupu do vyšší integrační úrovně.
Ilustrace workflow (panel detailu karty) je příklad, ne historie repozitáře.

## 1. Inventura: co dnes skutečně funguje

| Oblast | Stav | Kde |
|---|---|---|
| Větve | Jen `main` + ~60 krátkých `feat/fix/chore/perf` větví a ~60 worktrees (Codex, kancelář, ruční). Žádný `develop`, žádný `topic/`. | `git branch`, `git worktree list` |
| Ochrana main | **Nevynuceno**: GitHub branch protection 404, rulesets prázdné (ověřeno 2026-11-06). | `gh api .../branches/main/protection` |
| Slučování | Agent sám, **squash**, vlak PR zdola nahoru, rebase `--onto` + force-push s lease. Backend `gh`/`git merge` nevolá; GitHub je jen čtení. | `docs/cista-linie.md` §3, `backend/integrations/github_merge_transport.py` |
| Nasazení | Jen textové pravidlo (ff pull, build, restart 8740). Nasazené SHA se nikde neeviduje. | `docs/cista-linie.md` §4 |
| Náhled | `tools/serve-preview.py`: backend + `dist/` z worktree, kde skript leží, nad kopií dat (`--port`, `--data`); 8740/8768 chráněné. Build ani worktree sám nedělá. Velín o něm neví. | `tools/serve-preview.py` |
| Design náhled karty | Screenshoty na hlavu PR + „Potvrdit vzhled“ jen člověk; nová hlava = nový slot. | `docs/design-nahled.md` |
| Přijetí člověkem | Existuje jen pro **plán** (přijatá revize zadání) a pro **vzhled** (screenshoty). Pro kód/PR žádné; karta se uzavírá deterministicky (`done.confirmed, by: opora`). | `backend/canvas/opora_review_humans.py`, `docs/lokalni-slouceni.md` |
| Ticket / běh | Ticket nemá pole větev ani PR; `deliver` bere volitelné `sha`. Běh má vazbu PR (`opora_execution_pull_requests`: state, source, commit). | `backend/brain_opora/determinism/ticket_model.py` |
| Velín | 9 částí, nic o gitu, náhledech, PR ani nasazení. | `frontend/agi-pletor/dashboard/`, `backend/api/agi_pletor/dashboard_routes.py` |
| Pletor / srdce / dělníci | Postupy = skilly Dílny (`agent: pletor` do promptu, `agent: srdce` mezi postupy srdce). Žádný o větvích. | `backend/agi_pletor/pletor_opora_settings/skills/` |

## 2. Rozpory se zadáním a sjednocení

1. **Squash dlouhodobých vztahů.** Linie stavby slučuje vše squashem. Zadání: topic → develop a develop → main
   běžným merge commitem (ancestry), squash jen u krátké dokončené pracovní větve. → `docs/cista-linie.md` §3 se mění (viz §4 níže).
2. **Agent slučuje sám bez přijetí člověkem.** Zadání: do developu a mainu jen po přijetí konkrétního rozdílu (SHA + cíl)
   člověkem. → Přijetí je metadata ve Velínu; agent ho nesmí zapsat (routa jen člověk). Vlak PR zůstává pro pracovní větve
   uvnitř tématu; brána do developu/mainu je nová.
3. **Nasazení hned po sloučení.** Zadání: nasazení je samostatná akce a eviduje se SHA. → Velín drží `deployed {sha, at}`,
   zapisuje člověk po restartu; merge sám nic nenasazuje.
4. **Náhled = merge do mainu + restart 8740.** Zadání: náhled bez změny mainu. → Velín spouští `serve-preview.py` nad
   worktree větve na volném portu s oddělenou kopií dat.
5. **Karta se uzavírá po sloučení PR (auto-close).** Zůstává, ale „sloučení“ pro uzavření znamená sloučení do cílové větve
   tématu, ne do mainu. Beze změny kódu v M1; zapsáno jako otevřený bod.
6. **Rebase `--onto` + force-push** zůstává jen pro vlastní pracovní větev vlaku (vyjasněné vlastnictví). Sdílené
   `main`, `develop`, `topic/*` se nikdy nepřepisují.

Nezrušeno: vlak PR podle kontraktu, ponytail, úklid vlastních větví, PR Lens, self-merge uvnitř tématu po kontrolách.

## 3. Role větví (konvence, vztahy eviduje Velín)

Nahrazeno stromem větví: `2026-11-06-linie-strom-vetvi.md`.

| Větev | Z čeho | Do čeho | Slučování | Přijetí |
|---|---|---|---|---|
| `main` | — | — | merge commit z `develop` (PR) | člověk: vydání |
| `develop` | `main` | `main` | merge commit z `topic/*` nebo `feat/*` (PR) | člověk: přijatý přírůstek |
| `topic/<id>-<nazev>` | určený commit `develop` | `develop` | merge commit; opakovaně | člověk: celý rozdíl proti develop |
| `feat/<id>-<nazev>` | `topic/*`, jinak `develop` | rodič | squash nebo merge, podle závislostí | člověk: podoba a chování v náhledu |
| `experiment/<id>-<varianta>` | známý bod | nikam automaticky | — | člověk rozhodne, co převzít |
| `fix/<id>-<problem>` | větev s chybou | tatáž | squash | jako feat |
| `hotfix/<id>` | nasazené SHA | `main` + přenos do `develop` | merge | člověk |

Role větve se odvozuje z předpony. Přijetí je svázáno s `{branch, sha, target, at, by}`; nový commit na větvi
nebo jiný cíl = přijetí neplatí (zobrazí se jako „zastaralé“).

## 4. Změna pravidel linie stavby (`docs/cista-linie.md`)

- §1: vlak PR dál platí, ale vagony jsou `feat/*` uvnitř tématu a jejich base je rodič (topic/develop), ne main.
- §3: squash jen `feat/*`, `fix/*`; `topic → develop` a `develop → main` merge commitem. Do `develop` a `main` slučuje
  agent jen s platným přijetím ve Velínu pro přesně tu hlavu a ten cíl. Bez přijetí stop a hlášení.
- §4: nasazení je samostatný krok; po restartu zapsat nasazené SHA do Velínu.
- Nový §7: náhled z Velínu, ne restart 8740.

## 5. M1: nejmenší ucelený průchod

Téma M1 je tento kontrakt sám (`feat/velin-linie` z `main`; `develop` se zakládá z `main` jako cíl).

### Backend `backend/agi_pletor/linie/`

- `branches.py`: čtení gitu přes `integrations.gitio.git` (jen čtení): `main`/`develop` HEAD (lokál i `origin/`),
  seznam větví s rolí z předpony, `ahead/behind` vůči rodiči, `git log parent..branch`, `git diff --stat parent...branch`,
  stav pracovního stromu (větev, HEAD, necommitnuté změny), SHA, ze kterého běží tento server (`REPO_ROOT`).
- `previews.py`: registr `<data>/pletor/linie/previews.json` `{slug: {branch, worktree, port, pid, data, state, startedAt,
  sha, log}}`. Start: `git worktree add <data>/pletor/linie/previews/<slug>/tree <branch>` (prune, existující znovu použít),
  junction `node_modules` z `REPO_ROOT`, `npm run build` (vlákno na pozadí, log do souboru), kopie dat
  (`registry.sqlite` přes `sqlite3` backup + složka projektu bez `maps/`, `worktrees/`), pak `sys.executable
  tools/serve-preview.py --port --data` z worktree. Port první volný od 8790 (8740/8768/8780 nikdy). Stav
  `building | running | failed | stopped`, `running` se ověřuje živě (pid žije + port odpovídá). Stop = ukončit proces,
  worktree zůstane (úklid je samostatná akce `remove`).
- `acceptance.py`: `<data>/pletor/linie/acceptance.json` `{branch: {sha, target, at, note}}` a `deployed {sha, at}`.
  `valid = sha == aktuální HEAD větve`.
- `view.py`: jeden souhrn pro Velín.

### Routy `backend/api/agi_pletor/linie_routes.py` (prefix `/api/pletor/linie`, jen člověk)

- `GET /` → `{main, develop, server:{sha, dirty}, deployed, branches:[{name, role, parent, sha, ahead, behind,
  acceptance:{sha, target, at, valid}|null, preview:{slug,...}|null}], previews:[...], enforcement:"nevynuceno"}`.
- `GET /diff?branch&target` → `{commits:[...], stat:"...", files:n}` (rozdíl, který by přešel do cíle).
- `POST /previews {branch, project}` → spustí; `DELETE /previews/{slug}` → stop; `GET /previews/{slug}/log`.
- `POST /accept {branch, sha, target, note}` → zapíše přijetí; `DELETE /accept/{branch}` → zruší.
- `POST /deployed {sha}` → zapíše nasazené SHA.
- Agent (`X-Opora-Actor: agent`) dostane 403 na všechno; přijetí nejde zapsat jinak než z UI.

### Frontend `frontend/agi-pletor/dashboard/` část **Linie**

Kontrolní bod 2026-11-06 12:30 (commit 54c76a59): první podoba byla tabulka větví. Člověk ji odmítl („nedá se
zorientovat, žádný seznam větví“). Backend zůstává, UI se staví znovu jako **grafický pohled podle ilustrace**:

- `GET /api/pletor/linie/graph` → linie `main` (zelená), `develop` (modrá), pracovní větve tématu (oranžová, experiment
  fialová) s commity (nejstarší nahoře), odbočením z rodiče (merge-base) a sloučením zpět (merge commit), štítky
  „PR: přijato do <cíl>“ / „přijetí zastaralé“, bublinou „Náhled (ukázka v aplikaci)“ a odkazem na PR.
  Pracovní větev tématu = větev nesloučená do main se špičkou novější než špička main, nebo s přijetím či náhledem
  (shortcut do M2, kdy ji určí ticket).
- `components/LinieGraph.tsx` (SVG, `logic/linie-graph.ts` s testem) + tři karty vpravo PRACOVNÍ VĚTEV / DEVELOP / MAIN
  s akcemi (Spustit / Otevřít / Zastavit náhled, log selhání, rozdíl vůči rodiči, Přijmout / Zrušit přijetí, nasazené SHA).
  Žádná tabulka větví.
- Adresa náhledu je kořen aplikace s projektem (`/?project=…&workspace=main`), ne `?screen=pletor`.
- Štítek „nevynuceno“ u ochrany main/develop, dokud nejsou GitHub rulesets.

### Postupy pro Pletora, srdce a dělníky

Skill Dílny `git-linie` (`agent: pletor` i kopie `agent: srdce`): role větví, odkud větvit, co je přijetí, kdy stop,
náhled z Velínu, nasazení zvlášť, hlavní vlákno zadává a subagenti vykonávají, kontrolní bod před změnou směru.
Dělníci ho dostanou v ticketu přes `skills` (výchozí seznam `ticket_model` doplní `git-linie`).

### Ověření M1

- `uv run pytest backend/agi_pletor backend/api/agi_pletor`, `npm test`, `npm run build`.
- Scénář: náhled `feat/velin-linie` běží na vlastním portu nad kopií dat; `main` i `develop` beze změny; přijetí hlavy
  zapsáno; nový commit přijetí zneplatní; agent dostane 403.

## 6. Další milníky (po připomínkách)

- **M2** Vazba zadání → ticket → běh → větev → PR: ticket nese `branch`, `parent`, PR číslo; srdce zakládá
  `feat/<ticket>` z rodiče tématu; Velín ukazuje řetěz.
- **M3** Skutečný Git graf (`git log --graph` → data pro vykreslení) vedle plánované struktury; aktivní téma, další
  krok, blokace jako metadata.
- **M4** Brána merge: backend odmítne `local-merge` i zápis `merged` bez platného přijetí pro cíl `develop`/`main`;
  GitHub rulesets (vyžaduje oprávnění vlastníka repozitáře).
- **M5** Hotfix z nasazeného SHA, přenos do develop; úklid uzavřených témat.

## 7. Otevřené body

- Auto-close karty po merge PR bere dnes každý merge; po M2 má brát jen merge do cílové větve tématu.
- Kopie dat náhledu bere jen jeden projekt; víc projektů až na vyžádání.
- `develop` se zakládá z `main` při M1; dokud není přijatý první přírůstek, je totožný s `main`.
