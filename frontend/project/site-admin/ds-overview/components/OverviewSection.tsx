import { useState } from "react";
import type { designSummary } from "@/project/site-admin/logic/site-document";
import MarkdownPreview from "./MarkdownPreview";
import "../styles/ds-overview.css";

type Summary = ReturnType<typeof designSummary>;
const FACTS: [keyof Summary, string][] = [["themes", "témat"], ["colors", "barev"], ["styles", "typografických stylů"], ["families", "rodin písma"],
  ["fonts", "fontů"], ["spacing", "mezer"], ["radius", "zaoblení"], ["shadow", "stínů"], ["components", "komponent"], ["assets", "assetů"]];
const MAX_README = 200_000;

/** Overview: titulek systému, souhrn počtů a README (brand book) jako markdown editor s náhledem vedle. Dílek dostane
 *  hotové hodnoty a změny hlásí nahoru; uložení drží rodič. */
export default function OverviewSection({ title, readme, summary, onTitle, onReadme, onOpen }: {
  title: string; readme: string; summary: Summary; onTitle: (title: string) => void; onReadme: (readme: string) => void; onOpen: (section: "colors" | "typography" | "spacing" | "radius" | "shadow") => void;
}) {
  const [view, setView] = useState<"split" | "edit" | "preview">("split");
  const links: Partial<Record<keyof Summary, "colors" | "typography" | "spacing" | "radius" | "shadow">> = { colors: "colors", themes: "colors", styles: "typography", families: "typography", fonts: "typography", spacing: "spacing", radius: "radius", shadow: "shadow" };
  return <div className="ds-overview">
    <input className="ds-overview__title" aria-label="Název design systému" placeholder="Název systému (např. Tajemství OPORY)" value={title} maxLength={200} onChange={(event) => onTitle(event.target.value)}/>
    <ul className="ds-overview__facts" aria-label="Souhrn systému">
      {FACTS.map(([key, label]) => {
        const target = links[key];
        return <li key={key} className={"ds-overview__fact" + (summary[key] ? "" : " ds-overview__fact--zero")}>
          {target ? <button type="button" className="ds-overview__fact-link" onClick={() => onOpen(target)}><b className="ds-overview__count">{summary[key]}</b> {label}</button>
            : <><b className="ds-overview__count">{summary[key]}</b> {label}</>}
        </li>;
      })}
    </ul>
    <div className="ds-overview__readme-head">
      <h4 className="ds-overview__label">README · brand book</h4>
      <div className="ds-overview__views" role="group" aria-label="Zobrazení README">
        {(["edit", "split", "preview"] as const).map((mode) => <button key={mode} type="button" aria-pressed={view === mode}
          className={"ds-overview__view" + (view === mode ? " ds-overview__view--active" : "")} onClick={() => setView(mode)}>{mode === "edit" ? "Psát" : mode === "split" ? "Vedle sebe" : "Náhled"}</button>)}
      </div>
      <small className="ds-overview__size">{(new Blob([readme]).size / 1000).toFixed(1)} / 200 kB</small>
    </div>
    <div className={"ds-overview__readme ds-overview__readme--" + view}>
      {view !== "preview" && <textarea className="ds-overview__editor" aria-label="README design systému" value={readme} maxLength={MAX_README} spellCheck
        placeholder={"# Název\n\nJak web mluví (hlas a tón), co dělat a co ne.\n\n## Jak systém použít\n\n- Text v `body`, `ink` na `surface`."} onChange={(event) => onReadme(event.target.value)}/>}
      {view !== "edit" && <div className="ds-overview__preview" data-testid="readme-preview"><MarkdownPreview source={readme}/></div>}
    </div>
  </div>;
}
