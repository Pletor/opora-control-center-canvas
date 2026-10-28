# Detail Studia

Panel vpravo jako Inspector v TechViz; ve Skutečnosti jen čtení (`docs/studio.md` §3). Bez výběru ukazuje otevřenou úroveň (u ní všechny vazby úrovně), s výběrem kartu.

- `components/StudioDetail.tsx` – identita (druh, název, adresa, stav, souhrn), tlačítko „Otevřít v Editoru stránky“ / „Otevřít mapu domény“ (`onOpenEditor(params)`), účel.
- `components/DetailElement.tsx` – obsah Detailu prvku pod sebou, jen ke čtení: importuje dílky z `architecture-editor/element-detail/` (`AgentContextPanel`, řádka Proč, `BriefStatus` = kritéria dokončení a stav, `WorkTab` bez tlačítka Editoru, u komponenty `LinkList` příchozích a odchozích vazeb bez výběru druhého konce a bez volby „Co po vazbě teče“). Odkaz do Editoru stránky zůstává jeden, v identitě. Sekce (bez uzlu grafu) obsah Detailu prvku nemá.
- `logic/element-view.ts` (test vedle) – `elementView` skládá logiku Detailu prvku (`agentContext`, `whyChain`, `workView`, `nodeLinks` jen u komponenty) pro položku Studia; `logic/use-element-view.ts` čte zadání `useNodeSpec` (jen GET) a kartu ze sdíleného `useAgentState` (stejné čtení jako `useCardGuards`, nic se nepolluje navíc). Volá ho `Studio` jen ve vrstvě Skutečnost; fázi bere z Desktop stavu (`useStudioData().nodeStates`), uzavření z `facts.done`.
- `components/DetailSections.tsx` – vazby (souhrnné vazby úrovně; u komponenty je nahradí její přímé vazby z Detailu prvku, `links={false}`), díry mapy (karty a všeho pod ní) a cesty zákazníka s odznakem ověření (sdílená logika `domain-map/logic/journey-verification.ts`).
- `logic/detail-model.ts` – hotová data panelu.
- `styles/studio-detail.css`, blok `studio-detail`.
