# Studio · MODEL (technický model domény)

Čistý TypeScript model vrstvy **MODEL** Studia, kontrakt `docs/studio.md` §4. Etapa S4: typy, katalog, pravidla vazeb,
geometrie, návrh modelu z architektury a úložiště. Bez UI (S6) a bez simulace (S5). Převzato téměř 1:1 z vlastního
prototypu `04.Architektura-projektu/prototype` (nic z `vendor/`). Celá složka je určená k línému načtení (`import()`):
nic mimo ni ji zatím staticky neimportuje.

- `logic/model-types.ts` – `opora.studio-model/1`: `{schema, domainId, revision, nodes[], edges[]}`, uzel
  `{id, type, name, position, config, binding?: {nodeId}}`, hrana `{id, from, to, type, enabled, label?, condition?}`,
  port `{id, type, direction}`, 12 datových typů portu (`PORT_TYPES`), `emptyStudioModel`.
- `logic/catalog.ts` – katalog 68 typů / 227 portů (`catalog`, `componentType`, `portColor`). Data:
  `catalog-technology.ts` (5 technologických typů a jejich výchozí parametry), `catalog-cloud.ts` (30 cloudových),
  `catalog-base.ts` (33 obecných).
- `logic/connection-policy.ts` – role vazeb Studia v2 (`studio-roles/2`): HTTP jen na pozorované role
  (`observed-http-roles.ts`, data), řízený Pod přes Deployment, omezení událostí object-store a serverless.
  `TYPED_POLICY` = jen typy portů.
- `logic/model-rules.ts` – `createNode`, `connectionError` (výstup → vstup, stejný typ, role, bez duplicit),
  `connect` a `removeNode` (vrací nový model), `validateModel` (katalog, limity 1000 / 5000, vazby).
  `logic/connection-choices.ts` – nabídka cílů při tažení vazby.
- `logic/geometry.ts` – změřený rozměr karty (`observed-geometry.ts`, data), kotva portu, Deployment s Pody,
  podklad rodin typů (`architectureAreas`). `logic/routing.ts` – Bézier / zaoblená objížďka jedné vazby,
  `logic/studio-routing.ts` – strany portů a výběr trasy pro všechny vazby (`layoutStudioConnections`).
- `logic/model-proposal.ts` – `CARRIES_PORT_TYPE` (`navigation → http-request`, `data → data`,
  `command → record-command`, `event → event`) a `proposeModelFromArchitecture(graph, domainId)`: návrh bez ukládání.
- `logic/studio-model-api.ts` – `GET/PUT /api/studio/model?project=&domain=`, obranné čtení, 409 = konflikt;
  `logic/use-studio-model.ts` – hook (načtení, `save` s revizí, stav `conflict`, `reload`).

Datové tabulky (`catalog-*.ts`, `observed-*.ts`) jsou generované z prototypu, jeden záznam na řádek, takže drží limit
200 řádků; řádky jsou dlouhé. Ruční úpravy dat jen spolu s prototypem.

Rozdíly proti prototypu: model je jedna doména bez sektorů, stránek, úkolů a checkpointů (ty drží OPORA); uzel nemá
`contracts`, `lifecycle`, `implementation` ani `deployment` (Deployment se pozná podle typu `kubernetes-deployment`);
pravidla `studio-roles/1` (zmrazená pro staré uložené domény prototypu) a profil geometrie `prototype/1` se nepřebírají,
protože starší uložené modely tu nejsou. Výpočetní funkce `technology.mjs` přijdou se simulací (S5).

Backend katalog nevaliduje (jen tvar a limity, `backend/project/studio/README.md`), proto `validateModel` běží před
uložením ve frontendu.

Testy: `logic/*.test.ts` (`npm test`), převedené z `prototype/test/` (`connection-policy`, `model`, `connection-menu`,
`geometry`, `architecture-areas`, `routing`, `studio-routing`); matice rolí full80 je v testu zhuštěná na jedinečné dvojice.
