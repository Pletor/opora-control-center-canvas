import { useState } from "react";
import type { DesignComponent } from "@/project/site-admin/logic/site-document";
import MarkdownPreview from "@/project/site-admin/ds-overview/components/MarkdownPreview";
import { clampHeight, componentNameProblem, previewProblem } from "../logic/components";

/** Editor jedné komponenty: jméno (potvrdí se opuštěním pole), skupina, souhrn, výška, HTML náhledu a README
 *  s náhledem markdownu. Chyba náhledu se ukáže hned u pole; server stejný náhled odmítne. */
export default function ComponentEditor({ component, taken, onChange, onRemove }: {
  component: DesignComponent; taken: string[]; onChange: (component: DesignComponent) => void; onRemove: () => void;
}) {
  const [name, setName] = useState(component.name);
  const problem = name === component.name ? "" : componentNameProblem(name, taken, component.name);
  const unsafe = previewProblem(component.preview);
  const commit = () => { if (name !== component.name && !problem) onChange({ ...component, name }); else setName(component.name); };
  const set = (patch: Partial<DesignComponent>) => onChange({ ...component, ...patch });
  return <div className="ds-components__editor" data-testid={"ds-component-editor-" + component.name}>
    <div className="ds-components__fields">
      <label className="ds-components__field">Jméno
        <input className={"ds-components__input" + (problem ? " ds-components__input--problem" : "")} value={name} maxLength={64} spellCheck={false}
          onChange={(event) => setName(event.target.value)} onBlur={commit} onKeyDown={(event) => { if (event.key === "Enter") commit(); }}/>
        {problem && <small className="ds-components__problem">{problem}</small>}
      </label>
      <label className="ds-components__field">Skupina
        <input className="ds-components__input" value={component.group ?? ""} maxLength={64} placeholder="Actions, Forms, Layout…"
          onChange={(event) => set({ group: event.target.value || undefined })}/>
      </label>
      <label className="ds-components__field">Výška náhledu (px)
        <input className="ds-components__input" type="number" min={40} max={4000} value={component.height}
          onChange={(event) => set({ height: clampHeight(event.target.valueAsNumber) })}/>
      </label>
      <label className="ds-components__field ds-components__field--wide">Souhrn (jedna věta)
        <input className="ds-components__input" value={component.summary ?? ""} maxLength={400} placeholder="Jinak se vezme první věta README."
          onChange={(event) => set({ summary: event.target.value || undefined })}/>
      </label>
    </div>
    <label className="ds-components__field">HTML náhledu (fragment, bez skriptů; třídy a var(--token) z design systému)
      <textarea className={"ds-components__code" + (unsafe ? " ds-components__input--problem" : "")} rows={6} spellCheck={false} value={component.preview}
        aria-label={"HTML náhledu " + component.name} onChange={(event) => set({ preview: event.target.value })}/>
      {unsafe && <small className="ds-components__problem" role="alert">{unsafe}</small>}
    </label>
    <div className="ds-components__readme">
      <label className="ds-components__field">README (props, kdy použít a kdy ne)
        <textarea className="ds-components__code" rows={10} value={component.readme} maxLength={200_000}
          aria-label={"README " + component.name} onChange={(event) => set({ readme: event.target.value })}/>
      </label>
      <div className="ds-components__readme-preview"><MarkdownPreview source={component.readme}/></div>
    </div>
    <button type="button" className="ds-components__remove" onClick={onRemove}>Odebrat komponentu {component.name}</button>
  </div>;
}
