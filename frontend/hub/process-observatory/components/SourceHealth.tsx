import type { SourceChip } from "../logic/source-health";

type Props = { chips: SourceChip[]; transport: string; error: string };
const TRANSPORT: Record<string, string> = { sse: "push · SSE", poll: "polling (SSE nedostupné)", connecting: "připojuji…" };

/** Řádek „Zdroje“: čip na zdroj (stav · stáří) a vpravo, jak tok právě doručuje. */
export default function SourceHealth({ chips, transport, error }: Props) {
  return <div className="process-observatory__health" data-oh-field="sourceHealth">
    <span className="process-observatory__label">Zdroje</span>
    {chips.map((chip) => <span key={chip.id} className={`process-observatory__chip process-observatory__chip--${chip.tone}`} title={chip.tip} data-oh-source={chip.id}>
      <i className={`process-observatory__led process-observatory__led--${chip.tone}`} aria-hidden="true" />
      <b>{chip.name}</b><span>{chip.state}</span>
      {chip.age && <><span className="process-observatory__sep">·</span><span className="process-observatory__mono">{chip.age}</span></>}
    </span>)}
    <span className="process-observatory__transport">
      {error ? <span className="process-observatory__error">{error}</span> : TRANSPORT[transport] ?? transport}
      {" "}<span className="process-observatory__mono">/api/oporahub/events/stream</span>
    </span>
  </div>;
}
