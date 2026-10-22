import ReviewLensPanel from "@/hub/review-lens/components/ReviewLensPanel";
import type { LensState } from "@/hub/review-lens/logic/use-review-lens";

/** Záložka Lens: jen obal prostoru `hub/review-lens`; data čte drawer (odznak a zrcadlo je potřebují taky). */
export default function LensTab({ nodeId, lens }: { nodeId: string; lens: LensState }) {
  return <ReviewLensPanel nodeId={nodeId} state={lens} />;
}
