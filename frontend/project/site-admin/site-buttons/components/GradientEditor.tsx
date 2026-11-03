import { ColorField } from "@/project/site-admin/site-fields/components/Fields";
import { addStop, backgroundCss, MAX_STOPS, removeStop, withAngle, withStop } from "../logic/button-gradient";
import type { Gradient } from "../logic/button-model";

/** Barevný přechod: pruh s výsledkem, úhel a zastávky (barva a poloha 0–100 %), 2–8 zastávek. */
export default function GradientEditor({ value, aliases, onChange }: { value: Gradient; aliases: string[]; onChange: (value: Gradient) => void }) {
  const { angle, stops } = value.gradient;
  return <div className="site-buttons__gradient" data-testid="button-gradient">
    <span className="site-buttons__gradient-bar" style={{ background: backgroundCss(value) ?? undefined }} aria-hidden="true"/>
    <label className="site-buttons__gradient-angle">Úhel {angle}°
      <input type="range" min={0} max={360} step={5} value={angle} onChange={(event) => onChange(withAngle(value, Number(event.target.value)))}/>
    </label>
    {stops.map((stop, index) => <div key={index} className="site-buttons__stop">
      <ColorField label={`Zastávka ${index + 1}`} value={stop.color} aliases={aliases} onChange={(color) => onChange(withStop(value, index, { color }))}/>
      <label className="site-buttons__stop-position">Poloha %
        <input className="site-fields__input" type="number" min={0} max={100} value={Math.round(stop.position * 100)}
          onChange={(event) => onChange(withStop(value, index, { position: Number(event.target.value) / 100 }))}/>
      </label>
      <button type="button" className="site-buttons__icon" aria-label={`Odebrat zastávku ${index + 1}`} disabled={stops.length <= 2}
        onClick={() => onChange(removeStop(value, index))}>×</button>
    </div>)}
    <button type="button" className="site-buttons__add" disabled={stops.length >= MAX_STOPS} onClick={() => onChange(addStop(value))}>+ Zastávka</button>
  </div>;
}
