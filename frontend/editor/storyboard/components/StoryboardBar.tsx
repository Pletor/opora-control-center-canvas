// Lišta storyboardu: výběr karty, ukládání, obnovení, otevření v okně, kreslení k momentu, stažení, balíček pro render, smazání, nástroje plátna a stav.
// Dílek nic nedělá sám; každé tlačítko hlásí callback rodiči. Text štítku stavu skládá `logic/storyboard-status.ts`.
import type { ReactNode } from "react";
import type { StatusTone } from "../logic/storyboard-status";
import type { StoryboardStatus } from "../logic/use-storyboard-store";
import { TOOLS, type StageTool } from "./StoryboardStage";

export default function StoryboardBar({ picker, status, label, notice = "", review, dirty, readOnly, canPlace, tool, hasDraw, sketchLabel, sketchDisabled, onPackage, onSketch, onTool, onSave, onReload, onOpenWindow, onDraw, onDownload, onDelete }: {
  /** Výběr karty z rodiče; stojí na začátku lišty. */
  picker: ReactNode;
  status: StoryboardStatus;
  /** Štítek stavu: „Neuloženo · ukládám za chvíli“, „Ukládám…“, „Uloženo HH:MM · N komentářů čeká na agenta“, „Změněno jinde“. */
  label: { text: string; tone: StatusTone };
  /** Upozornění nezávislé na stavu ukládání (např. balíček se nevydal); vidí ho člověk v kterékoli záložce. */
  notice?: string;
  review?: ReactNode;
  dirty: boolean;
  readOnly: boolean;
  /** Animace má pole x a y, takže nástroj Umístit dává smysl. */
  canPlace: boolean;
  tool: StageTool;
  hasDraw: boolean;
  /** „Skica“, nebo „Zobrazit skicu“ v režimu jen ke čtení. */
  sketchLabel: string;
  sketchDisabled: boolean;
  onPackage: () => void;
  onSketch: () => void;
  onTool: (tool: StageTool) => void;
  onSave: () => void;
  onReload: () => void;
  onOpenWindow: () => void;
  onDraw: () => void;
  onDownload: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="storyboard__bar" role="toolbar" aria-label="Storyboard">
      {picker}
      <div className="storyboard__tools" role="group" aria-label="Nástroj plátna">
        {TOOLS.filter((x) => x.key !== "place" || canPlace).map((x) => (
          <button key={x.key} type="button" aria-pressed={tool === x.key} disabled={readOnly && x.key !== "select"} onClick={() => onTool(x.key)}>{x.label}</button>
        ))}
      </div>
      <button type="button" className="primary" disabled={readOnly || !dirty || status === "saving" || status === "conflict"} onClick={onSave}>Uložit</button>
      {review}
      <button type="button" onClick={onReload}>{status === "conflict" ? "Obnovit" : "Načíst znovu"}</button>
      <button type="button" onClick={onOpenWindow}>Otevřít v okně</button>
      <button type="button" disabled={sketchDisabled} onClick={onSketch}>{sketchLabel}</button>
      {hasDraw && <button type="button" onClick={onDraw}>Kreslit k momentu</button>}
      <button type="button" onClick={onDownload}>Stáhnout storyboard.json</button>
      <button type="button" onClick={onPackage}>Balíček pro render</button>
      <button type="button" className="danger" disabled={readOnly} onClick={onDelete}>Smazat storyboard</button>
      <span className={"storyboard__status" + (label.tone === "warn" ? " storyboard__status--conflict" : label.tone === "dirty" ? " storyboard__status--dirty" : "")} role="status">
        {label.text}
      </span>
      {notice && <span className="storyboard__status storyboard__status--conflict" role="alert">{notice}</span>}
    </div>
  );
}
