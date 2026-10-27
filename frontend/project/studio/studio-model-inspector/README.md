# Studio · MODEL · inspektor

Pravý panel vrstvy MODEL (`docs/studio.md` §3–4, etapa S6a), v MODELu místo detailu Skutečnosti.

- `components/ModelInspector.tsx` – rodič: nápověda bez výběru, komponenta, nebo vazba; akce hlásí nahoru (`InspectorActions`).
- `components/NodeInspector.tsx` – název, typ, vazba `binding.nodeId` na kartu OPORY domény se skutečným stavem,
  parametry simulace a smazání. `components/ParameterField.tsx` – číselné pole s mezemi (výčet jako výběr), zápis po
  opuštění pole / Enteru, chyba u pole.
- `components/EdgeInspector.tsx` – typ, odkud → kam, `enabled`, `label`, `condition`, smazání.
- `logic/inspector-fields.ts` – řádky parametrů (`parameterKeys`, `parameters`, výchozí hodnoty z `config`) a převod
  textu pole s kontrolou `validateModelConfig`.
- `styles/studio-model-inspector.css`, blok `studio-model-inspector`.
