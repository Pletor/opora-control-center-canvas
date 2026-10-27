# Studio · MODEL · editace

Vrstva **MODEL** jedné domény (`docs/studio.md` §1, §3, §4; etapa S6a). Celá složka (a dílky `studio-model-canvas/`,
`studio-model-palette/`, `studio-model-inspector/`) se načítá líně: `Studio.tsx` ji bere přes `React.lazy` /
`import()`, takže do hlavního bundlu nepatří ani model, ani katalog, ani simulace.

- `components/StudioModelWorkspace.tsx` – rodič a jediné místo, které model ukládá: katalog vlevo, lišta, plátno,
  inspektor vpravo; výběr, rozdělaná vazba (klik / tah port → port, Escape ruší), hlášky, klávesy (Delete, Escape,
  Ctrl+Z, Ctrl+Shift+Z / Ctrl+Y; v textovém poli patří klávesy poli).
- `components/ModelToolbar.tsx` – zpět / znovu, stav uložení (neuloženo, uloženo · r<revize>, konflikt 409 s
  „Načíst znovu“), Uložit a důvod, proč model neprošel kontrolou.
- `components/ModelEmptyOffer.tsx` – prázdný model: „Navrhnout z architektury“ (`proposeModelFromArchitecture`
  + `withSimulationDefaults`, jen návrh) nebo „Začít prázdný“; `components/ModelUnresolved.tsx` – nepřevedené vazby.
- `logic/model-edit.ts` – editace jako čisté funkce (přidání s výchozí simulací a volným místem, posun, propojení s
  pravidly a politikou definice, smazání i z plánu incidentů, název, vazba na kartu OPORY, parametr, vazba).
- `logic/model-history.ts` – zpět / znovu (100 kroků, psaní do pole se slévá). `logic/model-save.ts` – neuloženo
  (obsah bez revize), kontrola před uložením (`validateSimulationModel` = S4 `validateModel` + S5), klávesy.
- `logic/use-model-editor.ts` – hook nad `useStudioModel`: historie, uložená verze, revize přidaná až při uložení.
- `logic/proposal-rows.ts` – nepřevedené vazby návrhu jako řádky (jména karet a důvod).
- `styles/studio-model.css`, blok `studio-model`.

Scénáře a RUN (S6b) zatím nejsou.
