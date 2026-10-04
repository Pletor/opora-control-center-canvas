import type { NodeLink } from "../logic/agent-context";

type Props = {
  title: string;
  links: NodeLink[];
  empty: string;
  onSelect: (id: string) => void;
};

/** Seznam vazeb jedním směrem: druhý konec a port; klik přenese výběr na druhý konec. */
export default function LinkList({ title, links, empty, onSelect }: Props) {
  return (
    <section className="element-detail__links" aria-label={title}>
      <h4 className="element-detail__subtitle">{title}</h4>
      {links.length ? (
        <ul className="element-detail__list">
          {links.map((link) => (
            <li key={link.edgeId}>
              <button type="button" className="element-detail__link" onClick={() => onSelect(link.otherId)}>
                <span className="element-detail__link-name">{link.otherName}</span>
                <span className="element-detail__port">{link.port}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="element-detail__muted">{empty}</p>
      )}
    </section>
  );
}
