// Značka původu u každé položky panelu: ⚙ odvozeno ze záznamů, A dělník, ✦ srdce, H člověk.
// Člověk podle ní ví, čemu věřit bez kontroly a co je tvrzení nebo úsudek.
import type { TrailSource } from "../logic/card-trail";
import { sourceMark } from "../logic/trail-timeline";

export default function SourceMark({ source }: { source: TrailSource }) {
  const mark = sourceMark(source);
  return <i className={"block-panel__src block-panel__src--" + mark.tone} title={mark.title} aria-label={mark.title} data-oh-source={source}>{mark.glyph}</i>;
}
