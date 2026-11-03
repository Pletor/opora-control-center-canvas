import { PreviewStyle, TokensScope } from "@/project/site-admin/ds-preview/components/TokensScope";
import { WEB } from "@/project/site-admin/ds-preview/logic/components-scope";
import { LEVELS } from "../logic/appearance";

/** Ukázková stránka webu v tokenech projektu a s rozepsaným Vzhledem: nadpisy, text s odkazem, seznam, inverzní
 *  pruh a kontejner. Nic nemění, jen ukazuje. */
export default function AppearancePreview({ css, theme }: { css: string; theme: string }) {
  return <div className="site-appearance__preview" aria-label="Náhled vzhledu webu">
    <PreviewStyle css={css} name="appearance"/>
    <TokensScope theme={theme} className={WEB + " site-appearance__page"}>
      <div className="ds-container">
        {LEVELS.map((level) => { const Tag = level; return <Tag key={level}>Nadpis {level.toUpperCase()}</Tag>; })}
        <p className="subheading">Podnadpis uvádí, o čem sekce je.</p>
        <p>Běžný text odstavce s <a href="#ukazka" onClick={(event) => event.preventDefault()}>odkazem</a>, který po najetí změní barvu.</p>
        <ul><li>První odrážka</li><li>Druhá odrážka</li></ul>
        <ol><li>Číslovaný krok</li><li>Další krok</li></ol>
      </div>
      <div className="ds-inverse site-appearance__inverse">Inverzní text na tmavém pruhu</div>
    </TokensScope>
  </div>;
}
