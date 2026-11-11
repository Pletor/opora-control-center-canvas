// Kruh postupu a čtyři tečky pravd karty (plátno 3). Dostává hotový `FaceGrowth`, nic nepočítá.
import type { FaceGrowth } from "../logic/face-growth";

const CIRCUMFERENCE = 113; // 2π·18, poloměr kruhu ve viewBoxu 40×40

/** Kruh postupu v barvě tvaru karty; uprostřed procenta, karta bez kroků „—“. */
export function FaceRing({ growth, size = 40 }: { growth: FaceGrowth; size?: number }) {
  const share = (growth.percent ?? 0) / 100;
  return (
    <span className="card-face__ring" style={{ width: size, height: size }} data-oh-progress={growth.percent ?? ""}
      role="img" aria-label={growth.percent === null ? "Bez kroků" : `Postup ${growth.percent} %`}>
      <svg viewBox="0 0 40 40" aria-hidden="true">
        <circle className="card-face__ring-track" cx="20" cy="20" r="18" />
        <circle className="card-face__ring-fill" cx="20" cy="20" r="18" strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - share)} />
      </svg>
      <b>{growth.percent ?? "—"}</b>
    </span>
  );
}

const TRUTHS = [
  ["Z", "Záměr: karta má záměr nebo kroky"],
  ["K", "Zrcadlo kódu: kód odpovídá kartě"],
  ["S", "Skutečnost: sloučeno v main"],
  ["B", "Budoucnost po sloučení: čisté, dopad na sousedy, nebo konflikt"],
] as const;
const MARK_WORD = { ok: "ano", miss: "ne", wait: "zatím neměřeno", part: "zčásti", bad: "rozpor" } as const;

/** Čtyři pravdy vedle sebe: zelená = platí, modrá = zčásti, červená = rozpor, šedá = neplatí, čárkovaná = neměří se. */
export function FaceTruths({ growth }: { growth: FaceGrowth }) {
  return (
    <span className="card-face__truths" data-oh-truths={growth.truths.join(" ")}>
      {TRUTHS.map(([letter, title], index) => {
        const mark = growth.truths[index];
        return <span key={letter} className={"card-face__truth card-face__truth--" + mark} title={`${title} · ${MARK_WORD[mark]}`}>{letter}</span>;
      })}
    </span>
  );
}
