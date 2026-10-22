// Hlava vrstvy na plátně (návrh 1a: „SEKTOR Exekuční broker ✓2 ▸1 ◷1 ●1 ○1 · 6 karet · 5 vazeb next“): počty karet
// podle tónu tváře a kolik vazeb `next` vrstvu řadí do sloupců. Jen čte hotové tváře; nic neukládá.
import { TONES, TONE_GLYPH, TONE_LABEL, countTones } from "../logic/face-tones";
import type { CardFace } from "../logic/card-face";

export default function FaceSummary({ title, faces, nextEdges }: { title: string; faces: CardFace[]; nextEdges: number }) {
  const counts = countTones(faces);
  return (
    <div className="card-face-summary" data-oh-view="layer-summary">
      <span className="card-face-summary__eyebrow">{title ? "Sektor" : "Vrstva"}</span>
      <b className="card-face-summary__title">{title || "Projekt"}</b>
      {TONES.filter((tone) => counts[tone]).map((tone) => (
        <span key={tone} className={"card-face-summary__count card-face-summary__count--" + tone} title={TONE_LABEL[tone]}
          data-oh-tone={tone} data-oh-value={counts[tone]}>{TONE_GLYPH[tone]} {counts[tone]}</span>
      ))}
      <small className="card-face-summary__meta">{faces.length} karet · {nextEdges} vazeb next · sloupce = pořadí podle závislostí</small>
    </div>
  );
}
