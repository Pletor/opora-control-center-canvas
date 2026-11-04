import { useState } from "react";
import type { DesignComponent, Theme } from "@/project/site-admin/logic/site-document";
import MarkdownPreview from "@/project/site-admin/ds-overview/components/MarkdownPreview";
import { groupComponents, isGenerated, newComponent } from "../logic/components";
import ComponentPreview from "./ComponentPreview";
import ComponentEditor from "./ComponentEditor";
import "../styles/ds-components.css";

/** Components: komponenty po skupinách, každá s živým náhledem v sandbox iframu a popisem z README. Přepínač tématu
 *  platí jen pro náhledy. `Button` skládá server z Tlačítek webu, proto místo editoru vede tam. Seznam drží rodič;
 *  dílek hlásí celý nový seznam a nic neukládá. */
export default function ComponentsSection({ components, themes, theme, project, tokensCss, componentsCss, onChange, onOpenButtons }: {
  components: DesignComponent[]; themes: Theme[]; theme: string; project: string; tokensCss: string; componentsCss: string;
  onChange: (components: DesignComponent[]) => void; onOpenButtons: () => void;
}) {
  const [picked, setPicked] = useState(theme);
  const [open, setOpen] = useState("");
  const shown = themes.some((item) => item.id === picked) ? picked : themes[0]?.id ?? "light";
  const names = components.map((component) => component.name);
  const add = () => { const created = newComponent(names); onChange([...components, created]); setOpen(created.name); };
  const replace = (name: string, next: DesignComponent) => {
    onChange(components.map((component) => component.name === name ? next : component));
    if (next.name !== name) setOpen(next.name);
  };
  return <div className="ds-components">
    <div className="ds-components__bar">
      <label className="ds-components__theme">Téma náhledů
        <select className="ds-components__select" value={shown} onChange={(event) => setPicked(event.target.value)}>
          {themes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <small className="ds-components__hint">Náhledy stojí na tokens.css a components.css uložené revize; po Uložit se obnoví.</small>
      <button type="button" className="ds-components__add" onClick={add}>+ Komponenta</button>
    </div>
    {!components.length && <p className="ds-components__empty">Zatím žádné komponenty. Nastav Tlačítka webu (vznikne Button) nebo přidej vlastní.</p>}
    {groupComponents(components).map(({ group, items }) => <section key={group} className="ds-components__group" aria-label={"Skupina " + group}>
      <h3 className="ds-components__group-title">{group}</h3>
      {items.map((component) => {
        const generated = isGenerated(component);
        return <article key={component.name} className="ds-components__card" data-testid={"ds-component-" + component.name}>
          <ComponentPreview name={component.name} html={component.preview} height={component.height} theme={shown}
            project={project} tokensCss={tokensCss} componentsCss={componentsCss}/>
          <div className="ds-components__about">
            <h4 className="ds-components__name">{component.name}{generated && <small className="ds-components__badge">z Tlačítek webu</small>}</h4>
            {component.summary && <p className="ds-components__summary">{component.summary}</p>}
            {generated ? <button type="button" className="ds-components__toggle" onClick={onOpenButtons}>Upravit v Tlačítkách webu →</button>
              : <button type="button" className="ds-components__toggle" aria-expanded={open === component.name}
                onClick={() => setOpen(open === component.name ? "" : component.name)}>{open === component.name ? "Zavřít editor" : "Upravit"}</button>}
          </div>
          {open !== component.name && component.readme && <details className="ds-components__details"><summary>README</summary><MarkdownPreview source={component.readme}/></details>}
          {!generated && open === component.name && <ComponentEditor key={component.name} component={component} taken={names}
            onChange={(next) => replace(component.name, next)}
            onRemove={() => { onChange(components.filter((one) => one.name !== component.name)); setOpen(""); }}/>}
        </article>;
      })}
    </section>)}
  </div>;
}
