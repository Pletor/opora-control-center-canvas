// Animátor částic MODELu v kontextu: plátno ho vytvoří jednou a předá mu snímek běhu, vazby (uvnitř React Flow) si ho
// vezmou z kontextu a přihlásí své částice. Bez poskytovatele se nic nehýbe.
import { createContext, useContext, useEffect, useState } from "react";
import { browserMotionEnv } from "../../studio-motion/logic/particle-animator";
import { FlowAnimator, type RunFrame } from "./flow-animator";

export const FlowAnimatorContext = createContext<FlowAnimator | null>(null);
export const useFlowAnimatorContext = () => useContext(FlowAnimatorContext);

/** Jeden animátor na plátno, řízený snímkem běhu; po odpojení plátna smyčka stojí a posluchači jsou odhlášení. */
export function useFlowAnimator({ running, tick, key }: RunFrame): FlowAnimator {
  const [animator] = useState(() => new FlowAnimator(browserMotionEnv()));
  useEffect(() => { animator.attach(); return () => animator.detach(); }, [animator]);
  useEffect(() => { animator.setFrame({ running, tick, key }); }, [animator, running, tick, key]);
  return animator;
}
