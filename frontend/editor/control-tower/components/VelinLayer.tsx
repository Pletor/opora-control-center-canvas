// Jedna vrstva Velínu: vlevo jméno a počty podle tónu, vpravo sektory jako rámečky s pilulkami karet v pořadí
// grafu závislostí. Pilulka nese značku a slovo tónu (barva sama nic neříká); klik otevře detail karty.
import { TONES, TONE_GLYPH, TONE_LABEL, type Counts, type VelinLayer as Layer } from "../logic/velin-model";

export function VelinCounts({ counts }: { counts: Counts }) {
  return <div className="velin__counts">
    {TONES.filter(tone => counts[tone]).map(tone => <span key={tone} className={"velin__count velin__count--" + tone}
      title={TONE_LABEL[tone]} data-oh-tone={tone} data-oh-value={counts[tone]}>{TONE_GLYPH[tone]} {counts[tone]}</span>)}
  </div>;
}

export default function VelinLayer({ layer, onOpen }: { layer: Layer; onOpen: (nodeId: string) => void }) {
  return (
    <section className="velin__layer" data-oh-layer={layer.id || "none"}>
      <div className="velin__layer-head">
        <span className="velin__eyebrow">Vrstva</span>
        <h3 className="velin__layer-title">{layer.label}</h3>
        <VelinCounts counts={layer.counts} />
      </div>
      <div className="velin__sectors">
        {!layer.sectors.length && <p className="velin__muted">Filtru tu nic neodpovídá.</p>}
        {layer.sectors.map(sector => (
          <div key={sector.id || "loose"} className="velin__sector" data-oh-sector={sector.id}>
            <div className="velin__sector-head">
              <span className="velin__eyebrow">Sektor</span><b>{sector.name}</b>
              <span className="velin__grow" /><small>{sector.pills.length} {sector.pills.length === 1 ? "karta" : sector.pills.length < 5 ? "karty" : "karet"}</small>
            </div>
            <div className="velin__pills">
              {sector.pills.map(pill => (
                <button key={pill.nodeId} type="button" className={"velin__pill velin__pill--" + pill.tone} onClick={() => onOpen(pill.nodeId)}
                  title={`${pill.name} · ${TONE_LABEL[pill.tone]} · ${pill.face.stage} · ${pill.face.reason}${pill.face.pr ? " · " + pill.face.pr.label : ""}`}
                  data-oh-node-id={pill.nodeId} data-oh-tone={pill.tone} data-oh-stage={pill.face.raw.stage} data-oh-reason={pill.face.raw.reason}>
                  <span aria-hidden="true">{TONE_GLYPH[pill.tone]}</span> {pill.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
