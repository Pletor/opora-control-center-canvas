import { useMemo } from "react";
import { PreviewStyle, TokensScope } from "@/project/site-admin/ds-preview/components/TokensScope";
import { PREVIEW_RESET, scopeComponentsCss, WEB } from "@/project/site-admin/ds-preview/logic/components-scope";
import { buttonsCss } from "../logic/button-css";
import { SIZES, STATES, type Buttons, type StateName } from "../logic/button-model";
import { customCssPreview, REDUCED_MOTION_CSS } from "../logic/custom-css-preview";

/** Živý náhled: velké tlačítko ve stavu vybrané záložky, všechny velikosti (skutečný hover, focus a animace)
 *  a řada všech stavů vynucených třídou. Pod tím přepínač „omezit pohyb“ jako `prefers-reduced-motion`. */
export default function ButtonsPreview({ project, theme, componentsCss, buttons, customCss, slug, state, text, still, onText, onStill }: {
  project: string; theme: string; componentsCss: string; buttons: Buttons; customCss: Record<string, string>; slug: string; state: StateName;
  text: string; still: boolean; onText: (text: string) => void; onStill: (still: boolean) => void;
}) {
  // Uložené vlastní CSS je poslední vrstva `components.css`; náhled ho nahradí rozepsaným, aby smazané pravidlo zmizelo hned.
  const saved = useMemo(() => scopeComponentsCss(componentsCss.split("\n@layer custom {")[0], project), [componentsCss, project]);
  const draft = useMemo(() => buttonsCss(buttons), [buttons]);
  const custom = useMemo(() => Object.entries(customCss).map(([name, source]) => {
    const result = customCssPreview(name, source, project);
    return "css" in result ? result.css : "";
  }).join("\n"), [customCss, project]);
  const label = text || buttons.variants[slug]?.label || "Text tlačítka";
  const sample = (extra: string, key: string, disabled = false) =>
    <button key={key} type="button" className={`ds-btn ds-btn--${slug} ${extra}`} disabled={disabled} onClick={(event) => event.preventDefault()}>{label}</button>;
  return <div className="site-buttons__preview" data-testid="button-preview">
    <PreviewStyle css={[PREVIEW_RESET, saved, draft, custom, REDUCED_MOTION_CSS].join("\n")} name="buttons"/>
    <TokensScope theme={theme} className={WEB + " site-buttons__stage" + (still ? " ds-web--still" : "")}>
      <div className="site-buttons__hero">{sample(state === "default" ? "" : `ds-btn--is-${state}`, "hero", state === "disabled")}</div>
      <div className="site-buttons__row" aria-label="Velikosti">{SIZES.map((size) => sample(`ds-btn--${size}`, size))}</div>
      <div className="site-buttons__row" aria-label="Stavy">{STATES.map((item) => <span key={item.id} className="site-buttons__state-sample">
        {sample(item.id === "default" ? "ds-btn--sm" : `ds-btn--is-${item.id} ds-btn--sm`, item.id, item.id === "disabled")}
        <small className="site-buttons__state-name">{item.label}</small>
      </span>)}</div>
    </TokensScope>
    <div className="site-buttons__preview-tools">
      <input className="site-fields__input" value={text} placeholder="Text tlačítka" aria-label="Text tlačítka v náhledu" maxLength={40} onChange={(event) => onText(event.target.value)}/>
      <label className="site-buttons__toggle">
        <input type="checkbox" checked={still} onChange={(event) => onStill(event.target.checked)}/>Omezit pohyb (prefers-reduced-motion)
      </label>
    </div>
  </div>;
}
