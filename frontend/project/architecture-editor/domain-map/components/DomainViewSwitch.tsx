import type { DomainView } from "../../logic/editor-route";

const VIEWS: { value: DomainView; label: string; title: string }[] = [
  { value: "pages", label: "Stránky", title: "Karty stránek se sekcemi a cesty zákazníka" },
  { value: "studio", label: "Studio", title: "Tok podle druhu vazby a stav cest podle posledního ověření" },
];

/** Přepínač pohledu v hlavičce mapy domény: Stránky | Studio. Stav drží rodič, dílek jen hlásí volbu (`onChange`). */
export default function DomainViewSwitch({ view, onChange }: { view: DomainView; onChange: (view: DomainView) => void }) {
  return <div className="domain-map__views" role="tablist" aria-label="Pohled na doménu">
    {VIEWS.map((item) => <button type="button" key={item.value} role="tab" aria-selected={view === item.value} title={item.title}
      className={"domain-map__view" + (view === item.value ? " domain-map__view--active" : "")} data-testid={"architecture-domain-view-" + item.value}
      onClick={() => onChange(item.value)}>{item.label}</button>)}
  </div>;
}
