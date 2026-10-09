// Podněty k dalšímu vývoji: seznam ne-blokujících nálezů review a kritiků. Člověk podnět odškrtne
// (hotovo / vrátit) a odškrtnutý smí smazat. Dílek nic neukládá; změny bublají přes onStatus / onRemove
// a zapisuje je rodič (App) přes desktop.mutate(setIdeaStatus / removeIdea).
import { sortedIdeas, sourceLabel, type CardIdea, type IdeaStatus } from "@/editor/node-detail/ideas/logic/ideas-model";
import "@/editor/node-detail/ideas/styles/ideas.css";

export default function IdeasPanel({
  ideas,
  readOnly,
  busy,
  onStatus,
  onRemove,
}: {
  ideas: CardIdea[];
  readOnly: boolean;
  busy: boolean;
  onStatus: (id: string, status: IdeaStatus) => void;
  onRemove: (id: string) => void;
}) {
  if (!ideas.length) {
    return (
      <p className="ideas__empty" data-testid="ideas-empty">
        Zatím žádné podněty. Review a kritici sem zapisují nálezy, které nebrání MVP: etapa projde a nápad zůstane na později.
      </p>
    );
  }
  return (
    <ul className="ideas" data-testid="ideas-list">
      {sortedIdeas(ideas).map((idea) => (
        <li key={idea.id} className={"ideas__item" + (idea.status === "done" ? " ideas__item--done" : "")}>
          <label className="ideas__check">
            <input
              type="checkbox"
              checked={idea.status === "done"}
              disabled={readOnly || busy}
              aria-label={(idea.status === "done" ? "Vrátit podnět: " : "Odškrtnout podnět: ") + idea.text}
              onChange={(e) => onStatus(idea.id, e.target.checked ? "done" : "open")}
            />
            <span className="ideas__text">{idea.text}</span>
          </label>
          <span className="ideas__meta" title={idea.at}>
            {sourceLabel(idea.source)}{idea.by && idea.by !== "human" ? " · " + idea.by : ""}
          </span>
          {idea.status === "done" && !readOnly && (
            <button type="button" className="ideas__remove" disabled={busy} title="Smazat odškrtnutý podnět"
              aria-label={"Smazat podnět: " + idea.text} onClick={() => onRemove(idea.id)}>
              ×
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Tichý odznak s počtem otevřených podnětů (záložka detailu); nula se neukazuje. */
export function IdeasCount({ count }: { count: number }) {
  return count ? <span className="ideas__count" aria-label={`${count} otevřených podnětů`}>{count}</span> : null;
}
