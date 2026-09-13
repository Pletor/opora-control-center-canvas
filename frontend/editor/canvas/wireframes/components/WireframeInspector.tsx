import type { ChangeEvent } from "react";
import type { WireframeMetadata } from "@/editor/canvas/wireframes/logic/wireframe-model";

export type InspectableWireframe = {
  id: string;
  type: string;
  text?: string;
  name?: string | null;
  strokeColor: string;
  backgroundColor: string;
  metadata: WireframeMetadata;
};

export default function WireframeInspector({
  selected,
  disabled,
  onMetadata,
  onColors,
}: {
  selected: InspectableWireframe | null;
  disabled: boolean;
  onMetadata: (patch: Partial<WireframeMetadata>) => void;
  onColors: (colors: { strokeColor?: string; backgroundColor?: string }) => void;
}) {
  if (!selected)
    return (
      <aside className="wireframe-inspector" aria-label="Inspektor wireframu">
        Vyber wireframe blok nebo prvek.
      </aside>
    );
  const { metadata } = selected;
  const changeText = (field: "notes" | "action" | "behavior") =>
    (event: ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) =>
      onMetadata({ [field]: event.target.value });
  return (
    <aside className="wireframe-inspector" aria-label="Inspektor wireframu">
      <h3>Inspektor</h3>
      <p className="muted">{selected.name || selected.text || metadata.component}</p>
      <label>
        Poznámky
        <textarea disabled={disabled} value={metadata.notes} onChange={changeText("notes")} />
      </label>
      <label>
        Akce (popis, nevykonává se)
        <input disabled={disabled} value={metadata.action} onChange={changeText("action")} />
      </label>
      <label>
        Chování
        <input disabled={disabled} value={metadata.behavior} onChange={changeText("behavior")} />
      </label>
      <div className="wireframe-colors">
        <label>
          Tah
          <input type="color" disabled={disabled} value={selected.strokeColor} onChange={(event) => onColors({ strokeColor: event.target.value })} />
        </label>
        <label>
          Výplň
          <input type="color" disabled={disabled} value={selected.backgroundColor === "transparent" ? "#000000" : selected.backgroundColor} onChange={(event) => onColors({ backgroundColor: event.target.value })} />
        </label>
      </div>
      <label>
        Animace
        <select
          aria-label="Animace"
          disabled={disabled}
          value={metadata.animation.preset}
          onChange={(event) => onMetadata({ animation: { ...metadata.animation, preset: event.target.value as WireframeMetadata["animation"]["preset"] } })}
        >
          <option value="none">Bez animace</option>
          <option value="fade">Ztmavení</option>
          <option value="slide">Posun</option>
          <option value="scale">Měřítko</option>
        </select>
      </label>
      <label>
        Délka {metadata.animation.durationMs} ms
        <input type="range" min="0" max="4000" step="20" disabled={disabled} value={metadata.animation.durationMs} onChange={(event) => onMetadata({ animation: { ...metadata.animation, durationMs: Number(event.target.value) } })} />
      </label>
      <label>
        Zpoždění {metadata.animation.delayMs} ms
        <input type="range" min="0" max="4000" step="20" disabled={disabled} value={metadata.animation.delayMs} onChange={(event) => onMetadata({ animation: { ...metadata.animation, delayMs: Number(event.target.value) } })} />
      </label>
      <label className="wireframe-mode">
        <input type="checkbox" disabled={disabled} checked={metadata.parallax.enabled} onChange={(event) => onMetadata({ parallax: { ...metadata.parallax, enabled: event.target.checked } })} />
        Scroll parallax
      </label>
      <label>
        Rychlost {metadata.parallax.speed}
        <input type="range" min="-2" max="2" step="0.1" disabled={disabled || !metadata.parallax.enabled} value={metadata.parallax.speed} onChange={(event) => onMetadata({ parallax: { ...metadata.parallax, speed: Number(event.target.value) } })} />
      </label>
      <p className="muted">Pozice a velikost zůstávají nativními hodnotami Excalidrawu.</p>
    </aside>
  );
}
