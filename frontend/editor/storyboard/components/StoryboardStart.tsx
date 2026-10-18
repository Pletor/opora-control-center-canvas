// Karta zatím nemá storyboard: výběr animace a tlačítko Založit. Dílek jen hlásí zvolené id animace.
import { useState } from "react";
import { CODE_ANIMATION, SCENE_ANIMATION } from "../logic/storyboard-model";

export default function StoryboardStart({ animations, locked, onCreate }: {
  animations: { id: string; label: string }[];
  locked: boolean;
  onCreate: (animationId: string) => void;
}) {
  // Vlastní kód a webovou scénu nabízíme vždy, i kdyby je server v seznamu neposlal.
  const always = [{ id: CODE_ANIMATION, label: "Vlastní kód" }, { id: SCENE_ANIMATION, label: "Webová scéna" }];
  const options = [...animations, ...always.filter((a) => !animations.some((o) => o.id === a.id))];
  const [pick, setPick] = useState(options[0]?.id ?? "");
  return (
    <div className="storyboard__start">
      <p>Karta zatím nemá storyboard. Vyberte animaci a založte ho; pak ke každému momentu napište, co tam chcete jinak.</p>
      <label className="storyboard__field">Animace
        <select value={pick} onChange={(e) => setPick(e.target.value)}>{options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</select>
      </label>
      <button type="button" className="primary" disabled={locked || !pick} onClick={() => onCreate(pick)}>Založit storyboard</button>
      {locked && <p className="storyboard__status">Main je jen ke čtení.</p>}
    </div>
  );
}
