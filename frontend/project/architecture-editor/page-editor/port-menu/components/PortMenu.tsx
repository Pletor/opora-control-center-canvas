import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { CanvasNode, EdgeCarries } from "@/shared/types/logic/types";
import { EDGE_CARRIES } from "@/shared/types/logic/types";
import { CARRIES_LABEL } from "@/shared/edge-carries/logic/edge-carries";
import type { CatalogItem } from "@/editor/component-library/library-catalog/logic/library-catalog";
import { firstInPort, libraryForCarries, searchTargets, stepIndex } from "../logic/port-menu";
import "../styles/port-menu.css";

type Props = {
  sourceName: string; at: { x: number; y: number };
  /** Kompatibilní karty (`linkTargets`) a celá Knihovna; nabídka je jen filtruje hledáním a druhem toku. */
  targets: CanvasNode[]; items: CatalogItem[];
  onLink: (targetId: string, carries: EdgeCarries | null) => void; onCreate: (itemId: string) => void; onClose: () => void;
};
type Option = { id: string; kind: "link" | "create"; label: string; note: string };

/**
 * Nabídka vazby z výstupního portu: hledání, volba druhu toku a dvě části, „Existující karty“ a „Vytvořit
 * a propojit“. Šipky chodí po položkách, Enter vybírá, Escape a klik mimo zavírají. Nic neukládá, volbu hlásí nahoru.
 */
export default function PortMenu({ sourceName, at, targets, items, onLink, onCreate, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [carries, setCarries] = useState<EdgeCarries | null>(null);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement | null>(null);
  const close = useRef(onClose); close.current = onClose;
  const links: Option[] = searchTargets(targets, query).map((node) => ({ id: node.id, kind: "link", label: node.name, note: node.kind === "sector" ? "Sektor" : "Uzel" }));
  const creates: Option[] = libraryForCarries(items, carries, query).map((item) => ({ id: item.id, kind: "create", label: item.label, note: "vstup: " + CARRIES_LABEL[firstInPort(item)!.carries] }));
  const options = [...links, ...creates];
  const current = options[Math.min(active, options.length - 1)];
  const optionId = (option: Option) => `port-menu-${option.kind}-${option.id}`;
  useEffect(() => { setActive(0); }, [query, carries]);
  useEffect(() => { if (current) document.getElementById(optionId(current))?.scrollIntoView?.({ block: "nearest" }); }, [current?.id, current?.kind]);
  useEffect(() => {
    const outside = (event: PointerEvent) => { if (root.current && !root.current.contains(event.target as Node)) close.current(); };
    document.addEventListener("pointerdown", outside, true);
    return () => document.removeEventListener("pointerdown", outside, true);
  }, []);
  const choose = (option: Option | undefined) => { if (!option) return; if (option.kind === "link") onLink(option.id, carries); else onCreate(option.id); };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
    else if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setActive((index) => stepIndex(Math.min(index, options.length - 1), event.key === "ArrowDown" ? 1 : -1, options.length)); }
    else if (event.key === "Enter" && event.target instanceof HTMLInputElement) { event.preventDefault(); choose(current); }
  };
  const row = (option: Option) => <div key={optionId(option)} id={optionId(option)} role="option" aria-selected={option === current}
    className={"port-menu__option" + (option === current ? " port-menu__option--active" : "")} data-testid={optionId(option)}
    onPointerEnter={() => setActive(options.indexOf(option))} onClick={() => choose(option)}>
    <span className="port-menu__label">{option.label}</span><span className="port-menu__note">{option.note}</span>
  </div>;
  return <div className="port-menu" role="dialog" aria-label={`Vazba z ${sourceName}`} data-testid="port-menu" ref={root}
    style={{ left: at.x, top: at.y }} onKeyDown={onKeyDown}>
    <p className="port-menu__head">Vazba z <strong>{sourceName}</strong></p>
    <input className="port-menu__search" type="search" autoFocus placeholder="Hledat kartu nebo prvek…" aria-label="Hledat kartu nebo prvek"
      role="combobox" aria-expanded="true" aria-controls="port-menu-list" aria-activedescendant={current ? optionId(current) : undefined}
      value={query} onChange={(event) => setQuery(event.target.value)}/>
    <div className="port-menu__carries" role="group" aria-label="Co po vazbě teče">
      {[null, ...EDGE_CARRIES].map((value) => <button key={value ?? "none"} type="button" aria-pressed={carries === value}
        className={"port-menu__chip" + (value ? ` port-menu__chip--${value}` : "")} onClick={() => setCarries(value)}>{value ? CARRIES_LABEL[value] : "Neurčeno"}</button>)}
    </div>
    <div className="port-menu__list" id="port-menu-list" role="listbox" aria-label="Kam vazbu vést">
      <div role="group" aria-label="Existující karty"><p className="port-menu__section" aria-hidden="true">Existující karty</p>
        {links.length ? links.map(row) : <p className="port-menu__empty">Žádná kompatibilní karta.</p>}</div>
      <div role="group" aria-label="Vytvořit a propojit"><p className="port-menu__section" aria-hidden="true">Vytvořit a propojit</p>
        {creates.length ? creates.map(row) : <p className="port-menu__empty">Žádný prvek Knihovny s takovým vstupem.</p>}</div>
    </div>
  </div>;
}
