# Detail prvku

Pravý sloupec Editoru stránky (`docs/architektura-projektu.md`, krok 3). Nahoře **Pracovní kontext agenta** (prostředí, doména, stránka, komponenta / uzel, cesta v repozitáři), pod tím identita prvku a záložky **Zadání / Vazby / Práce**.

- `components/ElementDetail.tsx` skládá `AgentContextPanel`, `BriefTab` (s `IdentityForm`; vazby prvku jsou jen v záložce Vazby), `LinkList` a `WorkTab`.
- `logic/agent-context.ts` (test vedle): `agentContext` čte prostředí a host z `site.environments[0]` domény, stránku jako nejbližší prvek se `site.kind = "page"` (s `goal` a `feel`, jen když je člověk zadal; panel je pak ukáže jako Cíl stránky a Působení), cestu názvů pod stránkou a `sourceRef`; `origin: "planned"` je „Navržená cesta“ s upozorněním. Co v grafu není, je `null` → „nedostupné“. `nodeLinks` dělí vazby na příchozí a odchozí a u každé nese `carries`, jen když ho vazba má. `LinkList` dává u vazby `next` výběr „Co po vazbě teče“ (Navigace / Data / Příkaz / Událost / neurčeno) a změnu hlásí `onCarries(edgeId, carries | null)`; ukládá `ArchitectureEditor` přes `setEditorEdgeCarries` (`logic/editor-model.ts`).
- `logic/use-node-spec.ts` čte pracovní zadání **jen pro čtení** přes `GET /api/node-spec` (stejné API jako záložka Zadání v Editoru). Prázdné nebo nedostupné = „Zadání se doplňuje v Editoru“. Detail zadání nikdy nezapisuje.
- Mění se jen název a účel: koncept je lokální, uloží se přes `onIdentity` (chyba zůstane u formuláře, `disabled` zamkne pole). Vše ostatní hlásí callbackem (`onSelect`, `onOpenEditor`, `onClose`).
