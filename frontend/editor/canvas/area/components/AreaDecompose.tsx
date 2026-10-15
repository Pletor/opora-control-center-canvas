// Složený oddíl „Rozložit na sektory“ (oblast na kořenové vrstvě) nebo „Rozložit na karty“ (fáze uvnitř
// sektoru) v inspektoru oblasti: z hotového záměru ukáže zadání pro agenta-rozkladače a tlačítko, které
// ho zkopíruje do schránky. Nic neukládá ani nespouští — agenta spouští člověk v terminálu se skillem.
// Co se rozkládá, rozhodne `decomposeTarget` podle toho, zda oblast leží ve vrstvě sektoru (`host`);
// zadání skládá čistá funkce `decomposePrompt`; kopírování a hlášky obstará sdílený `useCopyText`.
import { czechCount } from "@/editor/canvas/area/logic/area-model";
import { decomposePrompt, decomposeTarget, type AreaHost } from "@/editor/canvas/area/logic/decompose-prompt";
import { COPY_FAILED_TEXT, useCopyText } from "@/shared/hooks/logic/use-copy-text";
import "@/editor/canvas/area/styles/area.css";

export default function AreaDecompose({
  project,
  workspace,
  areaId,
  areaName,
  intent,
  sectors,
  cards,
  host,
}: {
  project: string;
  workspace: string;
  areaId: string;
  areaName: string;
  /** Záměr tak, jak je uložený (`node.purpose`); rozepsaný text se sem dostane až po uložení. */
  intent: string;
  sectors: number;
  /** Karty (`kind: "node"`) uvnitř rámečku; u fáze sektoru je to, co už je pokryté. */
  cards: number;
  /** Sektor, v jehož vrstvě oblast leží; `null` na kořenové vrstvě. Spočítá rodič (App) z grafu. */
  host: AreaHost | null;
}) {
  const { status, copy, fieldRef } = useCopyText();
  const target = decomposeTarget(host);
  const prompt = decomposePrompt({ project, workspace, areaId, areaName, intent, sectors, cards, host });
  const state = target === "none"
    ? (host?.kind === "missing" ? "Rodič vrstvy oblasti v grafu chybí; rozklad není k dispozici." : "Oblast leží ve vnitřním plátně karty; rozklad na sektory ani karty se tu nenabízí.")
    : !intent.trim()
    ? "Nejdřív napište záměr."
    : !prompt
      ? "Zadání nejde sestavit: identifikátor projektu, workspace, oblasti nebo sektoru obsahuje nepovolené znaky."
      : target === "cards"
        ? cards > 0
          ? `Fáze sektoru „${host?.name}“ má ${czechCount(cards, "kartu", "karty", "karet")}; další rozklad přidá jen nepokrytou část akceptace sektoru.`
          : `Fáze sektoru „${host?.name}“: zkopírujte zadání a vložte ho agentovi v terminálu se skillem.`
        : sectors > 0
          ? `Oblast má ${czechCount(sectors, "sektor", "sektory", "sektorů")}; další rozklad přidá nové vedle nich.`
          : "Zkopírujte zadání a vložte ho agentovi v terminálu se skillem.";

  return (
    <details className="area-decompose" data-testid="area-decompose" data-target={target}>
      <summary className="area-decompose__summary">{target === "cards" ? "Rozložit na karty" : target === "none" ? "Rozložit" : "Rozložit na sektory"}</summary>
      <p className="muted area-decompose__state">{state}</p>
      {prompt && (
        <>
          <textarea
            ref={fieldRef}
            className="area-decompose__prompt"
            aria-label="Zadání pro agenta-rozkladače"
            data-testid="area-decompose-prompt"
            readOnly
            rows={10}
            value={prompt}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="area-decompose__actions">
            <span className="area-decompose__status" role="status">{status === "copied" ? "Zkopírováno" : ""}</span>
            <button type="button" onClick={() => void copy(prompt)} data-testid="area-decompose-copy">
              Kopírovat zadání
            </button>
          </div>
          {status === "failed" && <p className="area-decompose__alert" role="alert">{COPY_FAILED_TEXT}</p>}
        </>
      )}
    </details>
  );
}
