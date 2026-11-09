// Rodič karty: nahoře tvář karty z agent-state (`editor/canvas/card-face`: druh, kdo drží, název, jeden stavový
// řádek, postup kroků, nejvýš jedna patička), pod ní sekce, technologie a stavy komponenty (jen když jsou zapsané), bloky obsahu s porty a u vybrané karty štítky a jeden fold
// „Podrobnosti“. Kontrolní pás, kuličky pipeline, sloty dokladů a starší stavové věty z karty zmizely; žijí
// v detailu karty. `data` nenese žádnou funkci, takže `memo` kartu opravdu přeskočí, když se data nezměnila
// (docs/navrhy/2026-10-14-vykon-platna.md, oprava 3). Pod prahem zoomu (`logic/card-lod.ts`) kreslí nevybraná
// karta jen glyf, z bloků číslo, název a úchyty; nevybraná karta má bloky vždy zjednodušené.
import { memo, useMemo } from "react";
import { useStore, type Node, type NodeProps } from "@xyflow/react";
import CardDetails from "./CardDetails";
import type { EffectiveRule } from "../logic/effective-rules";
import type { Rule } from "@/shared/desktop-state/logic/types";
import type { SourceRef } from "@/shared/types/logic/types";
import CardBody from "@/editor/canvas/node-card/components/CardBody";
import CardComponent from "@/editor/canvas/node-card/components/CardComponent";
import CardProgress from "./CardProgress";
import CardBlocks, { type CardBlockHandlers } from "@/editor/canvas/node-card/components/CardBlocks";
import CardFoot from "@/editor/canvas/node-card/components/CardFoot";
import CardPorts, { type BlockPort } from "@/editor/canvas/node-card/components/CardPorts";
import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import { useCardActions, type CardActions } from "@/editor/canvas/node-card/logic/card-actions";
import { cardDetail, farZoomSelector, type CardDetail } from "@/editor/canvas/node-card/logic/card-lod";
import CardFace, { CardGlyph } from "@/editor/canvas/card-face/components/CardFace";
import type { CardFace as Face } from "@/editor/canvas/card-face/logic/card-face";
import "@/editor/canvas/node-card/styles/node-card.css";

/** Data karty: jen hodnoty (žádné funkce), aby šla porovnat se starou verzí (board/logic/stable-nodes.ts). */
export type NodeCardData = {
  /** Tvář karty z `cards[]` agent-state (jediný zdroj stavu); chybí jen u starých testovacích dat. */
  face?: Face;
  moved?: boolean;
  work?: import("../logic/use-work-overview").WorkRow;
  realization?: { value?: import("@/shared/types/logic/types").CanvasNode["realization"]; status?: import("../logic/use-source-status").SourceStatus; disabled: boolean };
  autonomous?: boolean;
  evidence?: import("./CardEvidence").CompletionEvidence;
  lease?: import("../logic/use-leases").CardLease;
  /** Lease jde uvolnit (karta ho má a plátno zná projekt). */
  releaseLease?: boolean;
  frontier?: import("../logic/use-frontier").FrontierItem;
  upstream?: { rows: import("../logic/upstream").UpstreamRow[] };
  inheritedRules?: EffectiveRule[];
  rules?: { items: Rule[] };
  source?: { source: SourceRef; project: string; workspace: string };
  view: CardView;
  rename: { editing: boolean };
  ports: { open: BlockPort[] };
  /** Bloky obsahu v kartě i jejich porty jsou jen ke čtení (plátno zamčené nebo karta uzavřená). */
  blocks: { disabled: boolean };
  /** Filtr štítků: karta bez vybraného štítku je ztlumená. */
  dimmed: boolean;
  /** Id bloku vybraného na plátně (jen pro vybraný uzel); zvýrazní jeho rámeček v kartě. */
  selectedBlockId?: string;
};

/** Obsluha dílků karty z jednoho stabilního objektu akcí; mění se jen s id karty. */
function useCardHandlers(actions: CardActions, id: string) {
  return useMemo(() => {
    const block = (event: Parameters<CardActions["cardBlock"]>[1]) => actions.cardBlock(id, event);
    const blocks: CardBlockHandlers = {
      add: () => block({ type: "add" }),
      move: (blockId, delta) => block({ type: "move", blockId, delta }),
      remove: (blockId) => block({ type: "remove", blockId }),
      rename: (blockId, title) => block({ type: "rename", blockId, title }),
      text: (blockId, text) => block({ type: "text", blockId, text }),
      addPort: (blockId) => block({ type: "add-port", blockId }),
      renamePort: (blockId, portId, label) => block({ type: "rename-port", blockId, portId, label }),
      removePort: (blockId, portId) => block({ type: "remove-port", blockId, portId }),
      decidePort: (blockId, portId, status, reason) => block({ type: "decide-port", blockId, portId, status, reason }),
    };
    return {
      blocks,
      rename: { start: () => actions.renameStart(id), cancel: () => actions.renameCancel(id), commit: (name: string) => actions.renameCommit(id, name) },
      toggle: (port: BlockPort) => actions.togglePort(id, port),
      confirm: () => actions.confirm(id),
      realize: (commit: string, prUrl: string) => actions.realize(id, commit, prUrl),
      release: () => actions.releaseLease(id),
      history: () => actions.history(id),
      trail: () => actions.trail(id),
    };
  }, [actions, id]);
}

/** Karta bez napojení na React Flow store: detail dostává zvenku (testy, měření). */
export function NodeCardView({ id, data, selected, detail }: { id: string; data: NodeCardData; selected: boolean; detail: CardDetail }) {
  const actions = useCardActions();
  const on = useCardHandlers(actions, id);
  const { view, blocks, dimmed, selectedBlockId } = data;
  const full = detail === "full";
  const sector = view.kind === "sector";
  const far = !full && !!data.face;
  const title = <CardBody id={id} name={view.name} purpose={selected ? view.purpose : undefined} rename={{ ...on.rename, editing: data.rename.editing }} />;
  return (
    <div
      className={
        "node-card node-card--lean" + (data.face ? " node-card--face-" + data.face.state : "") +
        (data.moved ? " node-card__added-pulse" : "") +
        (sector ? " node-card--sector" : "") +
        (selected ? " node-card--selected" : " node-card--compact") +
        (full ? "" : " node-card--far") +
        (dimmed ? " node-card--dimmed" : "") +
        (view.closed ? " node-card--closed" : "")
        + (data.realization?.status?.status === "missing" ? " node-card--source-missing" : "")
      }
      data-testid={"node-card-" + id}
      data-detail={detail}
    >
      {far ? <CardGlyph face={data.face!} name={view.name} /> : data.face ? <CardFace face={data.face} title={title} onHistory={on.history} onTrail={on.trail} /> : title}
      {!far && <CardComponent tech={view.tech} states={view.states} section={view.section} />}
      {!far && <CardProgress view={view} face={data.face} />}
      <CardBlocks id={id} rows={view.rows} disabled={blocks.disabled} handlers={on.blocks} selectedBlockId={selectedBlockId} selected={selected}
        detail={selected ? detail : "far"} />
      {selected && <CardDetails id={id} data={data} actions={actions} release={data.releaseLease ? on.release : undefined} realize={on.realize} />}
      {selected && <CardFoot view={view} onTag={actions.tag} />}
      <CardPorts id={id} open={data.ports.open} onToggle={on.toggle} />
    </div>
  );
}

const NodeCard = memo(function NodeCard({ id, data, selected }: NodeProps<Node<NodeCardData>>) {
  // Jediný boolean ze store: karta se překreslí jen při překročení prahu, ne v každém snímku zoomu.
  const far = useStore(farZoomSelector);
  return <NodeCardView id={id} data={data} selected={!!selected} detail={cardDetail(far, !!selected)} />;
});

export default NodeCard;
