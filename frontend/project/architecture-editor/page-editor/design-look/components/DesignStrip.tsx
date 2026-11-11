import type { DesignTokens } from "@/project/site-admin/logic/site-document";
import { designButton, designFonts, designSwatches, type Look } from "../logic/design-look";
import "../styles/design-look.css";

/** Přepínač Layout | Design vrstvy 1; změnu hlásí rodiči (stav v adrese drží `useLook`). */
export function LookSwitch({ look, onChange }: { look: Look; onChange: (look: Look) => void }) {
  return <div className="design-look__switch" role="group" aria-label="Pohled layoutu">
    {(["layout", "design"] as const).map((value) => <button key={value} type="button" className="design-look__switch-option" aria-pressed={look === value}
      data-testid={"architecture-look-" + value} onClick={() => onChange(value)}>{value === "layout" ? "Layout" : "Design"}</button>)}
  </div>;
}

type Props = { tokens: DesignTokens | null; onOpenSite?: () => void };

/** Pruh Design webu nad mřížkou v pohledu Design: barevné vzorky, písma a ukázka tlačítka z Design systému projektu
 * a odkaz do Správy webu. Bez tokenů řekne, že design zatím není (nebo nejde načíst). */
export default function DesignStrip({ tokens, onOpenSite }: Props) {
  const swatches = tokens ? designSwatches(tokens) : [];
  const fonts = tokens ? designFonts(tokens) : [];
  const button = tokens && designButton(tokens);
  return <section className="design-look" aria-label="Design webu" data-testid="architecture-design-strip">
    <strong className="design-look__title">Design webu</strong>
    {swatches.length > 0 && <span className="design-look__swatches">
      {swatches.map((swatch) => <span key={swatch.name} className="design-look__swatch" style={{ background: swatch.color }} title={`${swatch.name} ${swatch.color}`}/>)}
    </span>}
    {fonts.map((font) => <span key={font.name} className="design-look__font" style={{ fontFamily: font.stack }} title={font.stack}>Aa <small>{font.name}</small></span>)}
    {button && <span className="design-look__button" style={{ background: button.background, color: button.color, borderRadius: button.radius, fontFamily: button.font }}>Tlačítko</span>}
    {!swatches.length && !fonts.length && <span className="design-look__hint">{tokens ? "Design systém zatím nemá barvy ani písma." : "Design systém projektu se nepodařilo načíst."}</span>}
    {onOpenSite && <button type="button" className="design-look__open" onClick={onOpenSite}>Správa webu →</button>}
  </section>;
}
