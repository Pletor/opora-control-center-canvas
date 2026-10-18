// Sekce Duel Schránky (docs/schranka-duel.md §4): konverzace jako v terminálu, žádná klikačka. Bez vybraného duelu
// seznam duelů rozsahu a představa s trendem; v duelu stopa A/B a výměn, vedle nekalibrovanou sílu argumentů pro B s rozpadem. Dole jediný
// vstup: co text znamená, určí `parseDuelCommand`, a teprve platný příkaz odejde (Enter) přes `vaultOp`.
// Seznam duelů a fokus skládá rodič (BriefVaultDock); otevřený duel tu běží živě (poll 3 s, po zápisu hned).
import { useState } from "react";
import { ApiError } from "@/shared/types/logic/types";
import { useFragmentDetail } from "@/editor/node-detail/brief-vault/logic/use-brief-vault";
import { vaultOp, type VaultScope } from "../../logic/vault-actions";
import { COMMAND_HELP, OUTSIDE_HELP, parseDuelCommand, type DuelContext } from "../logic/duel-command";
import { humanSide, lessonNotice, trendLine, type DuelItem, type DuelWrite } from "../logic/duel-view";
import { useDuel, useVision } from "../logic/use-duel";
import DuelList from "./DuelList";
import DuelTrail from "./DuelTrail";
import DuelOdds from "./DuelOdds";
import DuelInput from "./DuelInput";
import "../styles/duel.css";

export default function DuelSection({ scope, vaultScope, items, visionKey, focus, readOnly }: {
  scope: VaultScope;
  /** Rozsah schránky (`""` = plátno), jde do `scopeNodeId` nového duelu a představy. */
  vaultScope: string;
  items: DuelItem[];
  /** Otisk představ ve stromu (id:revize): jeho změna načte představu a trend znovu. */
  visionKey: string;
  /** Fragment fokusu Schránky (subject nového duelu), nebo `null`. */
  focus: { id: string; title: string; discipline: string | null } | null;
  readOnly: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const duel = useDuel(scope, selected);
  const [notice, setNotice] = useState("");
  const vision = useVision(scope, vaultScope, visionKey);
  const fragment = useFragmentDetail(scope.project, scope.workspace, focus?.id ?? null, null, items);
  const data = duel.data;

  function context(): DuelContext {
    const text = fragment.detail?.fragment.text;
    return {
      project: scope.project, scopeNodeId: vaultScope,
      duel: data ? { fragmentId: data.duel.fragment.id, revision: data.duel.fragment.revision, decided: data.duel.status === "decided",
        turns: data.duel.turns ?? [], humanSide: humanSide(data.duel.turns ?? []) } : null,
      focus: !focus ? null : text == null ? { loading: true }
        : { fragmentId: focus.id, revision: fragment.detail!.fragment.revision, text, discipline: focus.discipline },
      vision: vision.data?.vision?.text ?? null,
    };
  }

  async function send(text: string): Promise<string> {
    if (selected && !data) return "Načítám duel, zkus to za chvíli.";
    const command = parseDuelCommand(text, context());
    if (!command.ok) return command.error;
    try {
      const result = await vaultOp<DuelWrite>(scope, command.body);
      // Odpověď zápisu nese nový stav duelu: promítne se hned, poll jen dorovná.
      if (command.body.op === "duel-open") setSelected(result.fragment?.id ?? null);
      else if (result.duel) duel.apply(result);
      setNotice(lessonNotice(result));
      return "";
    } catch (e) {
      void duel.refresh();
      const message = e instanceof Error ? e.message : String(e);
      return e instanceof ApiError && e.status === 409 ? `Mezitím se duel změnil (${message}). Načetl jsem nový stav, pošli to znovu.` : message;
    }
  }

  const head = selected ? (
    <div className="duel__bar">
      <button type="button" className="duel__back" onClick={() => { setSelected(null); setNotice(""); }}>← Duely</button>
      <strong className="duel__bar-title">{items.find((item) => item.id === selected)?.title ?? "Duel"}</strong>
    </div>
  ) : (
    <div className="duel__vision">
      <div><strong>Představa:</strong> {vision.data?.vision?.text ?? (vision.error ? "nelze načíst" : "zatím žádná (napiš „představa: …“)")}</div>
      <div className="duel__vision-trend">{trendLine(vision.data?.trajectory)}</div>
      <div className="duel__vision-trend">{focus ? `Nový duel se bude týkat fragmentu „${focus.title}“.` : "Bez fokusu se nový duel týká celého projektu (A = představa)."}</div>
    </div>
  );

  return (
    <div className="duel" data-testid="vault-duel">
      {head}
      {notice && <p className="duel__notice" role="status">{notice}</p>}
      <div className="duel__body">
        {!selected ? <DuelList items={items} onOpen={setSelected} />
          : duel.error && !data ? <p className="duel__error" role="alert">Duel nelze načíst: {duel.error}</p>
          : !data ? <p className="duel__empty" role="status">Načítám duel…</p>
          : (
            <div className="duel__layout">
              <div className="duel__stream"><DuelTrail duel={data.duel} /></div>
              <DuelOdds data={data} />
            </div>
          )}
      </div>
      <DuelInput readOnly={readOnly} onSend={send} help={selected ? COMMAND_HELP : OUTSIDE_HELP}
        placeholder={selected ? "A: tvůj argument (Enter odešle, Shift+Enter nový řádek)" : "duel: co chceš změnit (Enter odešle)"} />
    </div>
  );
}
