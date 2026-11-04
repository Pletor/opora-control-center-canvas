import CopyIdButton from "@/ui-kit/copy-id/components/CopyIdButton";

/** One shelf card: quiet badge and ID chip on top, the name in the middle, the count and tags under it and the entry at
 *  the bottom. A library folder says "Složka", a Brain library "Knihovna". `count = null` while its source is loading. */
export default function ShelfCard({ id, testId, badge, name, count, tags = [], onOpen }: {
  id: string; testId: string; badge: string; name: string; count: string | null; tags?: string[]; onOpen: () => void;
}) {
  return <article className="component-shelf__card" data-testid={"component-shelf-" + testId}>
    <div className="component-shelf__card-top">
      <span className="component-shelf__badge">{badge}</span>
      <CopyIdButton id={id} label="ID knihovny"/>
    </div>
    <h4 className="component-shelf__name">{name}</h4>
    <p className="component-shelf__count">{count ?? "načítám…"}</p>
    {tags.length > 0 && <p className="component-shelf__tags">{tags.map((tag) => <span key={tag} className="component-shelf__tag">#{tag}</span>)}</p>}
    <button type="button" className="component-shelf__enter" data-testid={"component-shelf-open-" + testId} onClick={onOpen}>Vstup do editoru</button>
  </article>;
}
