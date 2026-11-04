import { useState } from "react";
import type { Project } from "@/shared/types/logic/types";
import AdoptForm from "./AdoptForm";
import ContributeForm from "./ContributeForm";
import "../styles/library-actions.css";

type Props = {
  /** Kde plátno leží: knihovna člověka, knihovna agenta, nebo kopie v projektu. */
  place: "human" | "agent" | "project"; title: string; projects: Project[]; project: string; busy: boolean; empty: boolean;
  onAdopt: (project: string, nodeId: string) => void; onContribute: (folder: string, slug: string, title: string) => void; onPromote: () => void;
  /** Otevře dialog „Zadání pro agenta“ (`library-brief/`); otevírá ho rodič. */
  onBrief: () => void;
};

/** Akce plátna podle místa: z knihovny „Převzít do projektu“ (plátno bez verze převzít nejde), z kopie v projektu
 * „Uložit jako vylepšení“, z knihovny agenta navíc „Povýšit do knihovny člověka“. Formulář se otevře pod tlačítkem. */
export default function LibraryActions({ place, title, projects, project, busy, empty, onAdopt, onContribute, onPromote, onBrief }: Props) {
  const [open, setOpen] = useState<"adopt" | "contribute" | null>(null);
  const close = () => setOpen(null);
  return <div className="library-actions" data-testid="library-actions">
    <div className="library-actions__row">
      <button type="button" className="library-actions__button" disabled={busy || empty} data-testid="library-brief-open"
        title={empty ? "Plátno zatím nemá verzi" : "Text zadání karty vygenerovaný z plátna"} onClick={onBrief}>Zadání pro agenta</button>
      {place !== "project" && <button type="button" className="library-actions__button" disabled={busy || empty} data-testid="library-adopt"
        title={empty ? "Plátno zatím nemá verzi; nejdřív ho uložte" : "Odvozená kopie v projektu, projekt ji mění sám"} onClick={() => setOpen(open === "adopt" ? null : "adopt")}>Převzít do projektu</button>}
      {place === "project" && <button type="button" className="library-actions__button" disabled={busy || empty} data-testid="library-contribute"
        onClick={() => setOpen(open === "contribute" ? null : "contribute")}>Uložit jako vylepšení</button>}
      {place === "agent" && <button type="button" className="library-actions__button" disabled={busy} data-testid="library-promote" onClick={onPromote}>Povýšit do knihovny člověka</button>}
    </div>
    {open === "adopt" && <AdoptForm projects={projects} project={project} busy={busy} onAdopt={(target, nodeId) => { onAdopt(target, nodeId); close(); }} onCancel={close}/>}
    {open === "contribute" && <ContributeForm title={title} busy={busy} onContribute={(folder, slug, name) => { onContribute(folder, slug, name); close(); }} onCancel={close}/>}
  </div>;
}
