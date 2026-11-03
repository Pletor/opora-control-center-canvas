import CopyIdButton from "@/ui-kit/copy-id/components/CopyIdButton";
import { shelfId, type ShelfEntry } from "../logic/component-shelf";

/** One library card: quiet "Knihovna" label and ID chip on top, the family name in the middle, the count under it and the
 *  read-only entry at the bottom. `count = null` while its source is still loading. */
export default function ShelfCard({ entry, count, onOpen }: { entry: ShelfEntry; count: string | null; onOpen: () => void }) {
  return <article className="component-shelf__card" data-testid={"component-shelf-" + entry.id}>
    <div className="component-shelf__card-top">
      <span className="component-shelf__badge">Knihovna</span>
      <CopyIdButton id={shelfId(entry)} label="ID knihovny"/>
    </div>
    <h4 className="component-shelf__name">{entry.label}</h4>
    <p className="component-shelf__count">{count ?? "načítám…"}</p>
    <button type="button" className="component-shelf__enter" data-testid={"component-shelf-open-" + entry.id} onClick={onOpen}>Vstup do editoru</button>
  </article>;
}
