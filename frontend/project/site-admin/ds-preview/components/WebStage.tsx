import { useMemo, type ReactNode } from "react";
import { PREVIEW_RESET, scopeComponentsCss, WEB } from "../logic/components-scope";
import { PreviewStyle, TokensScope } from "./TokensScope";

/** Výřez webu nad tokeny a uloženým `components.css` projektu (hlavička, patička, cookie lišta, tlačítka).
 *  Prvek s `position: fixed` (cookie lišta) zůstane uvnitř výřezu, protože výřez má `transform`. */
export default function WebStage({ project, theme, componentsCss, name, className = "", children }: {
  project: string; theme: string; componentsCss: string; name: string; className?: string; children: ReactNode;
}) {
  const css = useMemo(() => `${PREVIEW_RESET}\n${scopeComponentsCss(componentsCss, project)}`, [componentsCss, project]);
  return <>
    <PreviewStyle css={css} name={name}/>
    <TokensScope theme={theme} className={WEB + (className ? " " + className : "")} style={{ transform: "translateZ(0)" }}>{children}</TokensScope>
  </>;
}
