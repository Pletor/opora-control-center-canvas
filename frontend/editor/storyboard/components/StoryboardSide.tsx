// Pravý sloupec módu: záložky „Moment | Kód animace | Podklady“ u animace z kódu, „Moment | Scéna | Podklady“
// u webové scény, „Moment | Podklady“ u šablony (tam navíc tlačítko „Použít jako vlastní kód“ nad záložkami). Dílek jen vybírá, co ukázat; formulář, editor kódu
// i podklady dostávají hotová data a změny hlásí rodiči.
import { useState, type ComponentProps } from "react";
import { CODE_ANIMATION, SCENE_ANIMATION, type CodeSpec, type SceneSpec } from "../logic/storyboard-model";
import AssetPanel from "./AssetPanel";
import CodePanel from "./CodePanel";
import MomentForm from "./MomentForm";
import ScenePanel from "./ScenePanel";

type Tab = "moment" | "code" | "scene" | "assets";

export default function StoryboardSide({ animationId, code, scene, readOnly, workerError, sceneError, slowMs, form, assets, onApplyCode, onApplyScene, onUseAsCode }: {
  animationId: string;
  code?: CodeSpec;
  scene?: SceneSpec;
  readOnly: boolean;
  workerError: string;
  sceneError: string;
  slowMs: number | null;
  form: ComponentProps<typeof MomentForm>;
  assets: ComponentProps<typeof AssetPanel>;
  onApplyCode: (code: CodeSpec) => void;
  onApplyScene: (scene: SceneSpec) => void;
  /** Zkopíruje zdroj šablony do storyboardu; od té chvíle je animace vlastní. */
  onUseAsCode: () => void;
}) {
  const [tab, setTab] = useState<Tab>("moment");
  const isCode = animationId === CODE_ANIMATION && !!code;
  const isScene = animationId === SCENE_ANIMATION && !!scene;
  const shown: Tab = (tab === "code" && !isCode) || (tab === "scene" && !isScene) ? "moment" : tab;
  const open = assets.assets.filter((a) => !a.answered).length;
  return (
    <div className="storyboard__side">
      {!isCode && !isScene && <button type="button" className="storyboard__use-code" disabled={readOnly} onClick={onUseAsCode}>Použít jako vlastní kód</button>}
      <div className="storyboard__tabs" role="tablist" aria-label="Pravý panel">
        <button type="button" role="tab" aria-selected={shown === "moment"} onClick={() => setTab("moment")}>Moment</button>
        {isCode && <button type="button" role="tab" aria-selected={shown === "code"} onClick={() => setTab("code")}>Kód animace</button>}
        {isScene && <button type="button" role="tab" aria-selected={shown === "scene"} onClick={() => setTab("scene")}>Scéna</button>}
        <button type="button" role="tab" aria-selected={shown === "assets"} onClick={() => setTab("assets")}>{open > 0 ? `Podklady (${open})` : "Podklady"}</button>
      </div>
      {shown === "code" && code
        ? <CodePanel code={code} readOnly={readOnly} workerError={workerError} slowMs={slowMs} onApply={onApplyCode} />
        : shown === "scene" && scene
          ? <ScenePanel scene={scene} readOnly={readOnly} sceneError={sceneError} onApply={onApplyScene} />
          : shown === "assets"
            ? <AssetPanel {...assets} />
            : <MomentForm {...form} />}
    </div>
  );
}
