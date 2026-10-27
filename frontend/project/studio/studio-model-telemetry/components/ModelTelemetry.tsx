import { portColor } from "../../model/logic/catalog";
import type { PortType } from "../../model/logic/model-types";
import type { EditModel, Selection } from "../../studio-model/logic/model-edit";
import { nodeIncidents } from "../../studio-model-run/logic/incident-plan";
import type { RunState } from "../../studio-model-run/logic/run-control";
import { edgeMetrics, nodeMetrics, type Metric, type Spark } from "../logic/telemetry-view";
import IncidentControls, { type IncidentActions } from "./IncidentControls";
import Sparkline from "./Sparkline";
import "../styles/studio-model-telemetry.css";

/** Panel telemetrie v inspektoru MODELu (prototyp „Model dashboard“ a metriky uzlu): pro vybranou komponentu nebo
 * vazbu aktuální vypočtené hodnoty jako dlaždice, krátká historie posledních ticků jako sparkliny a u komponenty
 * incidenty. Trvalé upozornění, že jde o výpočet modelu, ne o telemetrii projektu. */
export default function ModelTelemetry({ model, selection, run, actions }: { model: EditModel; selection: Selection; run: RunState; actions: IncidentActions }) {
  if (!selection) return null;
  const { sim, history } = run;
  const isNode = selection.kind === "node";
  const metrics: Metric[] = isNode ? nodeMetrics(sim.nodes[selection.id]) : edgeMetrics(sim.edges[selection.id]);
  const sparks: Spark[] = isNode
    ? [{ label: "Dokončeno / tick", values: (history.nodes[selection.id] ?? []).map((s) => s.completed), color: "#45baff", unit: "/s" },
       { label: "Využití", values: (history.nodes[selection.id] ?? []).map((s) => Math.round(s.utilization * 100)), color: "#e8b95b", unit: " %" },
       { label: "Odmítnuto / tick", values: (history.nodes[selection.id] ?? []).map((s) => s.rejected), color: "#ff7397", unit: "/s" }]
    : [{ label: "Přijato / tick", values: (history.edges[selection.id] ?? []).map((s) => s.accepted), color: portColor((model.edges.find((e) => e.id === selection.id)?.type ?? "data") as PortType), unit: "/s" },
       { label: "Odmítnuto / tick", values: (history.edges[selection.id] ?? []).map((s) => s.rejected), color: "#ff7397", unit: "/s" }];
  return <section className="studio-model-telemetry" aria-label="Telemetrie modelu" data-testid="studio-model-telemetry">
    <header className="studio-model-telemetry__head">
      <h3 className="studio-model-telemetry__heading">Telemetrie · tick {sim.tick}</h3>
      <span className="studio-model-telemetry__source">výpočet modelu</span>
    </header>
    <p className="studio-model-telemetry__notice">Výpočet modelu, ne telemetrie projektu: jednotky za modelovou sekundu, nikdy se nepíší do karet OPORY.</p>
    {metrics.length ? <dl className="studio-model-telemetry__metrics" data-testid="studio-model-telemetry-metrics">
      {metrics.map((metric) => <div key={metric.label} className={"studio-model-telemetry__metric" + (metric.alert ? " studio-model-telemetry__metric--alert" : "")}>
        <dt className="studio-model-telemetry__metric-label">{metric.label}</dt><dd className="studio-model-telemetry__metric-value">{metric.value}</dd>
      </div>)}
    </dl> : <p className="studio-model-telemetry__notice">Spusťte nebo krokujte model; čísla se objeví po prvním ticku.</p>}
    {sparks.map((spark) => <Sparkline key={spark.label} spark={spark}/>)}
    {isNode && <IncidentControls key={selection.id} nodeId={selection.id} tick={sim.tick} planned={nodeIncidents(model, selection.id)} actions={actions}/>}
  </section>;
}
