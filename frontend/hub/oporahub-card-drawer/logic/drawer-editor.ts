import type { CanvasNode, Workspace } from "@/shared/types/logic/types";
import type { FragmentRef } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";

// Co detail karty potřebuje od Editoru: ponechané editory (pracovní zadání, popis, nastavení karty,
// paměť agenta, worktree) ukládají přes rodiče (App), který drží graf, zámek a revizi. Detail sám
// graf neukládá; bez Editoru (jen OporaHub) jsou editory jen ke čtení.
export type DrawerEditor = {
  readOnly: boolean;
  busy: boolean;
  workspaces: Workspace[];
  /** Revize výsledků Desktop v3 (obnoví Schránku a paměť agenta). */
  resultRevision: number;
  /** Obnoví uložené pracovní zadání po přijetí návrhu jinde. */
  specRefreshRevision: number;
  onSave: (node: CanvasNode) => void;
  /** Lidské uzavření karty po sloučení PR (`done` přes desktop-state rodiče); vrací chybu, nebo "" při úspěchu. */
  onCloseCard?: (nodeId: string, note: string) => Promise<string>;
  /** Otevře modal „Nový worktree“ pro kartu (detail se předtím zavře, aby modal nebyl pod ním). */
  onWorkspace: () => void;
  onOpenNode: (id: string) => void;
  onOpenVault?: (scope: string, focus?: string) => void;
  fragmentRefs: (nodeId: string) => FragmentRef[] | undefined;
};
