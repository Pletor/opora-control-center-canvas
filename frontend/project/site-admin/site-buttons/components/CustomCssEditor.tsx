import { useRef } from "react";
import type { SiteInvalid } from "@/project/site-admin/logic/site-admin-api";
import { customCssPreview } from "../logic/custom-css-preview";

const EXAMPLE = `/* :scope je tlačítko. Příklad: lesk přejede při najetí. */
:scope { position: relative; overflow: hidden; }
:scope::after { content: ""; position: absolute; inset: 0; background: linear-gradient(120deg, transparent 30%, rgba(255,255,255,.45), transparent 70%); transform: translateX(-100%); }
:scope:hover::after { animation: shine 700ms ease-out; }
@keyframes shine { to { transform: translateX(100%); } }`;

/** Vlastní CSS varianty: textarea s čísly řádků, chyba náhledu hned při psaní a chyba serveru (422) z posledního
 *  uložení na řádku, pod tím poznámky serveru k variantě (kontrast, focus ring). */
export default function CustomCssEditor({ slug, project, value, invalid, notes, onChange }: {
  slug: string; project: string; value: string; invalid: SiteInvalid | null; notes: string[]; onChange: (value: string) => void;
}) {
  const gutter = useRef<HTMLDivElement>(null);
  const preview = value.trim() ? customCssPreview(slug, value, project) : null;
  const local = preview && "problem" in preview ? preview.problem : null;
  const server = invalid?.path === `settings.customCss.button.${slug}` ? invalid : null;
  const marked = new Set([local?.line, server?.line].filter(Boolean));
  const lines = Math.max(value.split("\n").length, 6);
  return <fieldset className="site-buttons__group" data-testid="button-custom-css">
    <legend className="site-buttons__legend">Vlastní CSS s animací <code>.ds-btn--{slug}</code></legend>
    <p className="site-buttons__hint">CSS relativně k <code>:scope</code> (= tlačítko): <code>transition</code>, <code>@keyframes</code>, <code>::before</code>/<code>::after</code>, <code>@media</code>. Server ho při uložení sanitizuje a přidá vypnutí pohybu pro <code>prefers-reduced-motion</code>.</p>
    <div className="site-buttons__code">
      <div ref={gutter} className="site-buttons__gutter" aria-hidden="true">
        {Array.from({ length: lines }, (_item, index) => <span key={index} className={"site-buttons__line" + (marked.has(index + 1) ? " site-buttons__line--bad" : "")}>{index + 1}</span>)}
      </div>
      <textarea className="site-buttons__textarea" value={value} rows={lines} wrap="off" spellCheck={false} aria-label={`Vlastní CSS varianty ${slug}`}
        placeholder={EXAMPLE} aria-invalid={!!(local || server)} onChange={(event) => onChange(event.target.value)}
        onScroll={(event) => { if (gutter.current) gutter.current.scrollTop = event.currentTarget.scrollTop; }}/>
    </div>
    {!value.trim() && <button type="button" className="site-buttons__add" onClick={() => onChange(EXAMPLE)}>Vložit příklad animace</button>}
    {server && <p className="site-buttons__problem" role="alert" data-testid="button-css-422">Server odmítl uložení, řádek {server.line}: {server.reason}</p>}
    {local && <p className="site-buttons__problem" role="status">Náhled, řádek {local.line}: {local.reason}</p>}
    {!!notes.length && <ul className="site-buttons__notes" aria-label="Poznámky serveru k variantě">{notes.map((note, index) => <li key={index} className="site-buttons__note">{note}</li>)}</ul>}
  </fieldset>;
}
