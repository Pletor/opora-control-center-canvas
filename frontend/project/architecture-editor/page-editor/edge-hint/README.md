# Popisek vazby

Dílek Editoru stránky. Když člověk na mapě najede myší na vazbu, u kurzoru se ukáže bublinka: „zdroj → cíl“ (názvy uzlů) a druh toku česky (`CARRIES_LABEL` ze `shared/edge-carries`, stejné popisky jako v Detailu prvku → Vazby). Vazba `next` bez `carries` hlásí „Neurčeno – nastavte v Detailu prvku → Vazby“; vazby, které druh toku nést nemohou (`flow`, `rule`, `block`), to říkají také.

- `logic/edge-hint.ts` – čistá funkce `edgeHintText(edge, graph)`, test `edge-hint.test.ts`.
- `components/EdgeHint.tsx` – jen vykreslí hotový text na souřadnicích od rodiče.
- Rodič `ArchitectureCanvas` drží najetou vazbu (`onEdgeMouseEnter/Move/Leave`). Nic se neukládá.
