import HeartCanvas from "@/project/heart-canvas/components/HeartCanvas";
import "../styles/heart-screen.css";

/** Samostatná obrazovka srdce (`screen=heart`): vlastní hlavička s návratem na stránku projektu a pod ní celé plátno 1.
 * Nepatří do architektury projektu, proto nemá její lištu ani menu Editoru. */
export default function HeartScreen({ project, projectName, onBack }: { project: string; projectName?: string; onBack: () => void }) {
  return <div className="heart-screen" data-testid="heart-screen">
    <header className="heart-screen__head">
      <button type="button" className="heart-screen__back" data-testid="heart-screen-back" onClick={onBack}>← Projekt</button>
      <h1 className="heart-screen__title">Srdce projektu<small className="heart-screen__project">{projectName ?? project}</small></h1>
      <span className="heart-screen__tag">plátno 1 · LLM řídící projekt</span>
    </header>
    <div className="heart-screen__canvas"><HeartCanvas key={project} project={project}/></div>
  </div>;
}
