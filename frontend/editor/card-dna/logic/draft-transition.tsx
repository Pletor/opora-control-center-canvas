import { createContext, useContext } from "react";

export type DraftTransition = (change: () => void) => Promise<boolean>;
/** Panel hlásí úmysl rodiči dialogu; save scope a rozhodnutí o odmountování patří rodiči. */
export const DraftTransitionContext = createContext<DraftTransition>(async () => false);
export const useDraftTransition = () => useContext(DraftTransitionContext);
