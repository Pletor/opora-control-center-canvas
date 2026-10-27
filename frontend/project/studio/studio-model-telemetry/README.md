# Studio · MODEL · telemetrie

Panel telemetrie v inspektoru MODELu (`docs/studio.md` §5, etapa S6b; prototyp `model-panels.mjs`, Model dashboard).
Rodič (`StudioModelWorkspace`) ho skládá do slotu `telemetry` inspektoru.

- `components/ModelTelemetry.tsx` – vybraná komponenta nebo vazba: aktuální vypočtené hodnoty, sparkliny posledních ticků,
  u komponenty incidenty; trvalé upozornění, že jde o výpočet modelu.
- `components/Sparkline.tsx` – lomená čára SVG s poslední hodnotou a maximem.
- `components/IncidentControls.tsx` – Crash / Slow ×5 / Restore hned do běhu, „Uložit jako plánovaný incident“ (prázdný tick = další tick běhu), plán komponenty.
- `logic/telemetry-view.ts` – řádky hodnot uzlu a vazby, body sparkliny.
- `styles/studio-model-telemetry.css`, blok `studio-model-telemetry`.
