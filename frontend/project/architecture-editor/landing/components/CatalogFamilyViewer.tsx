import type { CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";

const DIRECTION = { in: "vstup", out: "výstup" } as const;

function Fact({ term, children }: { term: string; children: string }) {
  return <><dt className="component-shelf__term">{term}</dt><dd className="component-shelf__value">{children}</dd></>;
}

/** Read-only templates of one library family: name, purpose, tech, states, ports and the code template (folded). */
export default function CatalogFamilyViewer({ items }: { items: CatalogItem[] }) {
  return <ul className="component-shelf__list" data-testid="component-shelf-catalog">
    {items.map((item) => <li key={item.id} className="component-shelf__item">
      <div className="component-shelf__item-head"><h5 className="component-shelf__item-name">{item.label}</h5><code className="component-shelf__code">{item.id}</code></div>
      <p className="component-shelf__purpose">{item.purpose}</p>
      <dl className="component-shelf__facts">
        {item.tech && <Fact term="Tech">{item.tech}</Fact>}
        {!!item.states?.length && <Fact term="Stavy">{item.states.join(" · ")}</Fact>}
        {!!item.ports?.length && <Fact term="Porty">{item.ports.map((port) => `${port.id} (${DIRECTION[port.direction]}, ${port.carries})`).join(" · ")}</Fact>}
        <Fact term="Hotovo">{item.done.join(" ")}</Fact>
      </dl>
      {item.template && <details className="component-shelf__template"><summary className="component-shelf__summary">Šablona</summary><pre className="component-shelf__pre">{item.template}</pre></details>}
    </li>)}
  </ul>;
}
