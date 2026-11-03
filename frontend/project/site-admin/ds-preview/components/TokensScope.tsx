import type { CSSProperties, ReactNode } from "react";
import { SCOPE, scopeTokensCss } from "../logic/tokens-scope";

/** Jednou na stránku: vygenerovaný `tokens.css` uložené revize, uzavřený do `.ds-scope` (rodič ho načítá). */
export function TokensStyle({ css, project }: { css: string; project: string }) {
  return <style data-testid="site-tokens-css">{scopeTokensCss(css, project)}</style>;
}

/** Náhled nad tokeny projektu v daném tématu: uvnitř platí `var(--token)` a třídy stylů webu, ne aplikace. */
export function TokensScope({ theme, className = "", style, children }: { theme: string; className?: string; style?: CSSProperties; children: ReactNode }) {
  return <div className={SCOPE + (className ? " " + className : "")} data-theme={theme} style={style}>{children}</div>;
}

/** CSS náhledu webu (uzavřený `components.css` nebo neuložené úpravy), už přepsaný na selektory pod `.ds-web`. */
export function PreviewStyle({ css, name }: { css: string; name: string }) {
  return <style data-testid={"site-preview-css-" + name}>{css}</style>;
}
