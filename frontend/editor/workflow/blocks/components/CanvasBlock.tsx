// Rodič bloku na plátně (typ React Flow uzlu „block“): podle portu vloží Akce, Pravidla nebo Podklady do rámu.
// Drží jediný zámek zápisu bloku; mutace stavu posílá přes BlockApi rodiče (App).
import { memo, useState } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import BlockFrame from "@/editor/workflow/blocks/components/BlockFrame";
import ActionsBlock from "@/editor/workflow/blocks/components/ActionsBlock";
import RulesBlock from "@/editor/workflow/blocks/components/RulesBlock";
import MaterialsBlock from "@/editor/workflow/blocks/components/MaterialsBlock";
import {
  addMaterial, addRule, captionMaterial, materialKindOf, moveAction, moveMaterial, moveRule, removeAction, removeMaterial, removeRule, type BlockData,
} from "@/editor/workflow/blocks/logic/block-model";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import "@/editor/workflow/blocks/styles/blocks.css";

const CanvasBlock = memo(function CanvasBlock({ data }: NodeProps<Node<BlockData>>) {
  const { nodeId, nodeName, port, actions, rules, materials, readOnly, api } = data;
  const [busy, setBusy] = useState(false);
  async function run(fn: (current: DesktopState) => DesktopState): Promise<boolean> {
    if (busy) return false;
    setBusy(true);
    try {
      return await api.current.mutate(fn);
    } finally {
      setBusy(false);
    }
  }
  const disabled = readOnly || busy;
  return (
    <BlockFrame
      nodeId={nodeId}
      nodeName={nodeName}
      port={port}
      note={port === "action" ? "Proveď následující pipeline v tomto pořadí:" : port === "rule" ? "Pro tento uzel platí:" : "Obrázky a odkazy, které agent dostane jako podklad:"}
      onClose={() => api.current.close(nodeId, port)}
    >
      {port === "action" ? (
        <ActionsBlock
          actions={actions}
          disabled={disabled}
          onMove={(index, delta) => run(moveAction(nodeId, index, delta))}
          onRemove={(id) => run(removeAction(nodeId, id))}
          onAdd={() => api.current.pickPipeline(nodeId)}
        />
      ) : port === "rule" ? (
        <RulesBlock
          rules={rules}
          disabled={disabled}
          readOnly={readOnly}
          onMove={(index, delta) => run(moveRule(nodeId, index, delta))}
          onRemove={(id) => run(removeRule(nodeId, id))}
          onAdd={(text, kind) => run(addRule(nodeId, text, kind))}
        />
      ) : (
        <MaterialsBlock
          materials={materials}
          disabled={disabled}
          readOnly={readOnly}
          previewUrl={(material) => api.current.previewUrl(nodeId, material)}
          onMove={(index, delta) => run(moveMaterial(nodeId, index, delta))}
          onRemove={(material) => run(removeMaterial(nodeId, material.id)).then((ok) => { if (ok && material.kind === "upload") api.current.discardUpload(nodeId, material.path); })}
          onCaption={(id, caption) => run(captionMaterial(nodeId, id, caption))}
          onAddRef={(path, caption) => run(addMaterial(nodeId, materialKindOf(path), path.trim(), caption))}
          onUpload={async (dataUrl, caption) => {
            const file = await api.current.uploadMaterial(nodeId, dataUrl);
            return file ? run(addMaterial(nodeId, "upload", file, caption)) : false;
          }}
        />
      )}
    </BlockFrame>
  );
});

export const blockNodeTypes = { block: CanvasBlock };
export default CanvasBlock;
