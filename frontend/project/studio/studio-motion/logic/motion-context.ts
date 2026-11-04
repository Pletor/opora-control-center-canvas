// Animátor plátna pro vazby: plátno ho vytvoří jednou, vazby (uvnitř React Flow) si ho vezmou z kontextu a přihlásí
// své tečky. Bez poskytovatele (např. v testu nebo mimo plátno) se nic nehýbe.
import { createContext, useContext, useEffect, useState } from "react";
import { browserMotionEnv, ParticleAnimator } from "@/shared/flow-editor/flow-motion/logic/particle-animator";

export const MotionContext = createContext<ParticleAnimator | null>(null);
export const useMotionAnimator = () => useContext(MotionContext);

/** Jeden animátor na plátno; po odpojení plátna se smyčka zastaví a posluchači odhlásí. */
export function useParticleAnimator(): ParticleAnimator {
  const [animator] = useState(() => new ParticleAnimator(browserMotionEnv()));
  useEffect(() => { animator.attach(); return () => animator.detach(); }, [animator]);
  return animator;
}
