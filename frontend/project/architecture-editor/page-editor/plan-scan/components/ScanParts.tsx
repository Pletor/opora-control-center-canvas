import { useState } from "react";
import type { DesignTokens } from "@/project/site-admin/logic/site-document";
import type { ScanProposal } from "../logic/page-scan";
import type { AdoptParts } from "../logic/adopt-scan";
import { mergeDesignTokens } from "../logic/scan-design";
import { flowSize } from "../logic/scan-flow";
import { logicLook } from "../../element-palette/logic/logic-groups";
import { czechCount } from "../../layout-canvas/logic/czech-count";
import LayoutCanvas from "../../layout-canvas/components/LayoutCanvas";

const NO_LOGIC = { whole: [], byBox: new Map(), legacy: 0 };
const NO_STATES = new Map();
const noop = () => undefined;

type Props = {
  proposal: ScanProposal;
  /** Uložené tokeny Design systému (staré → nové); `null` = nenačtené. */
  tokens: DesignTokens | null;
  /** Adresa snímku skenu podle jména souboru. */
  captureSrc: (name: string) => string;
  layoutLock: string | null; contentLock: string | null;
  adopting: boolean; discardError: string;
  onAdopt: (parts: AdoptParts) => void; onDiscard: () => void;
};

/** Návrh skenu po třech částech se samostatnými zaškrtávátky (výchozí vše): Layout (boxy a funkčnost), Design (výřezy
 * boxů, snímek stránky, změny tokenů staré → nové) a Logika a tok dat (prvky a počet kroků toku). Volbu hlásí `onAdopt`. */
export default function ScanParts({ proposal, tokens, captureSrc, layoutLock, contentLock, adopting, discardError, onAdopt, onDiscard }: Props) {
  const [parts, setParts] = useState<AdoptParts>({ layout: true, design: true, logic: true });
  const chosen: AdoptParts = { ...parts, layout: parts.layout && !layoutLock };
  const crops = Object.entries(proposal.captures?.sections ?? {});
  const changes = tokens && proposal.design ? mergeDesignTokens(tokens, proposal.design).changes : [];
  const hasDesign = crops.length > 0 || !!proposal.captures?.page || !!proposal.design;
  const toggle = (key: keyof AdoptParts, label: string, disabled = false) => <label className="plan-scan__part-check">
    <input type="checkbox" checked={chosen[key]} disabled={disabled || adopting} data-testid={"architecture-scan-part-" + key}
      onChange={(event) => setParts({ ...parts, [key]: event.target.checked })}/> <strong>{label}</strong></label>;
  return <>
    <section className="plan-scan__part" aria-label="Layout">
      {toggle("layout", `Layout · ${czechCount(proposal.sections.length, ["box", "boxy", "boxů"])} s funkčností`, !!layoutLock)}
      <div className="plan-scan__preview">
        <LayoutCanvas preview layer="layout" sections={proposal.sections} logic={NO_LOGIC} states={NO_STATES} selectedId={null}
          layoutDisabled logicDisabled onLayout={noop} onSelect={noop} onRemoveElement={noop} onCarry={noop}/>
      </div>
      {layoutLock && <p className="plan-scan__hint">{layoutLock}</p>}
    </section>
    <section className="plan-scan__part" aria-label="Design">
      {toggle("design", "Design · tokeny webu a výřezy boxů", !hasDesign)}
      {!hasDesign && <p className="plan-scan__hint">Sken design nevrátil.</p>}
      {(proposal.captures?.page || crops.length > 0) && <div className="plan-scan__shots">
        {proposal.captures?.page && <figure className="plan-scan__shot plan-scan__shot--page"><img src={captureSrc(proposal.captures.page)} alt="Snímek celé stránky" loading="lazy"/>
          <figcaption>Celá stránka</figcaption></figure>}
        {crops.map(([id, name]) => <figure key={id} className="plan-scan__shot"><img src={captureSrc(name)} alt={"Výřez boxu " + id} loading="lazy"/>
          <figcaption>{proposal.sections.find((section) => section.id === id)?.name ?? id}</figcaption></figure>)}
      </div>}
      {proposal.captures?.page && <p className="plan-scan__hint">Snímek celé stránky zůstane jen tady: stránka zatím nemá vlastní inspiraci.</p>}
      {contentLock && crops.length > 0 && <p className="plan-scan__hint">Výřezy se jako inspirace nepřevezmou: {contentLock}</p>}
      {proposal.design && (!tokens ? <p className="plan-scan__hint">Design systém projektu se nepodařilo načíst; změny tokenů ukáže až zápis.</p>
        : changes.length ? <ul className="plan-scan__changes" aria-label="Změny tokenů">
          {changes.map((change) => <li key={change.path}><code>{change.path}</code> <span className="plan-scan__change-old">{change.before ?? "nový"}</span> → <span>{change.after}</span></li>)}
        </ul> : <p className="plan-scan__hint">Design systém už tokeny návrhu má.</p>)}
    </section>
    <section className="plan-scan__part" aria-label="Logika a tok dat">
      {toggle("logic", `Logika a tok dat · ${czechCount(proposal.logic.length, ["prvek", "prvky", "prvků"])}`, !proposal.logic.length)}
      {proposal.logic.length ? <ul className="plan-scan__logic">
        {proposal.logic.map((item) => <li key={item.ref}><span className="plan-scan__logic-kind">{logicLook(item.kind).label}</span> {item.name}
          <small className="plan-scan__logic-box"> · {item.section ? proposal.sections.find((section) => section.id === item.section)?.name : "Celá stránka"}
            {item.flow && ` · tok ${czechCount(flowSize(item.flow), ["krok", "kroky", "kroků"])}`}</small></li>)}
      </ul> : <p className="plan-scan__hint">Sken nenavrhl žádné prvky logiky.</p>}
      {contentLock && proposal.logic.length > 0 && <p className="plan-scan__hint">Logika a tok dat se nepřevezmou: {contentLock}</p>}
    </section>
    {proposal.notes.length > 0 && <ul className="plan-scan__notes" aria-label="Poznámky skenu">{proposal.notes.map((note) => <li key={note}>{note}</li>)}</ul>}
    {discardError && <p className="plan-scan__error" role="alert">{discardError}</p>}
    <div className="plan-scan__actions">
      <button type="button" className="plan-scan__adopt" disabled={adopting || !(chosen.layout || chosen.design || chosen.logic)} data-testid="architecture-scan-adopt"
        onClick={() => onAdopt(chosen)}>{adopting ? "Převádím…" : "Převzít"}</button>
      <button type="button" disabled={adopting} data-testid="architecture-scan-discard" onClick={onDiscard}>Zahodit</button>
    </div>
    <p className="plan-scan__hint">Layout nahradí celý layout stránky (boxy jako Návrh čekají na Přijmout); Design zapíše tokeny do Design systému webu; Logika vloží prvky jedním plánem a prvkům s tokem založí plátno logiky.</p>
  </>;
}
