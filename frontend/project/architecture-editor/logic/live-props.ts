import type { CardRequest } from "../live-status/logic/session-state";
import type { HeartRequest } from "@/layout/heart-channel/logic/heart-api";

/** Co editor architektury potřebuje vědět o živé práci: schopnost projektu (od App) a akce, které jdou nahoru do App. */
export type ArchitectureLiveProps = {
  worktreeLive: boolean;
  onSwitchWorkspace: (id: string) => void; onAskHeart: (request: HeartRequest) => void; onCreateWorktree: (domainId: string) => void;
  /** Otevře kartu (App přepne prostor, je-li jiný). */
  onOpenCard: (request: CardRequest) => void;
  /** Otevře plátno záměru stránky (`projectView=intent&page=<id>`, vyřizuje App). */
  onOpenIntent?: (pageId: string) => void;
  /** Otevře Správu webu projektu (`projectView=site`, vyřizuje App). */
  onOpenSite?: () => void;
  /** Otevře plátno toku v knihovně (`projectView=library&flow=<id>`, vyřizuje App). */
  onOpenLibraryFlow?: (flowId: string) => void;
};
