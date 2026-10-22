// Tvář karty na plátně (návrh „Opora Editor — lean“, rámy 2a/2b): druh a kdo kartu drží, název, JEDEN stavový
// řádek, postup kroků a nejvýš jedna patička. Pod 45 % zoomu jen glyf: značka zdraví, název a lišta postupu.
// Všechno čte z hotové `CardFace` (agent-state); každý prvek nese `data-oh-*`, aby agent nečetl obrazovku.
import type { CSSProperties, ReactNode } from "react";
import type { CardFace as Face } from "../logic/card-face";
import { countdown } from "../logic/face-labels";
import { useNow } from "../logic/use-now";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/logic/open";
import "../styles/card-face.css";

function LeaseCountdown({ expiresAt }: { expiresAt: string }) {
  const now = useNow(1000, true);
  const left = countdown(expiresAt, now);
  return <span className="card-face__lease" data-oh-lease-expires={expiresAt}>lease {left}</span>;
}

function Footer({ face }: { face: Face }) {
  const footer = face.footer;
  if (!footer) return null;
  if (footer.kind === "decision") return (
    <button type="button" className="card-face__foot card-face__foot--decision nodrag" data-oh-decision={footer.id}
      data-oh-action-id={footer.actionId} onClick={() => openCardDrawer(face.nodeId)} title={footer.text}>
      <span className="card-face__foot-text">● {footer.text}</span><span aria-hidden="true">→</span>
    </button>);
  if (footer.kind === "blocked") return (
    <div className="card-face__foot" data-oh-blocked-by={footer.ids.join(" ")}>
      <span className="card-face__foot-label">čeká na</span><span className="card-face__foot-text">{footer.text}</span>
    </div>);
  return (
    <div className="card-face__foot" data-oh-gate-status={footer.status} data-oh-gate-rule={footer.rule ?? ""}>
      <span className="card-face__foot-label">brána</span>
      <span className={"card-face__chip card-face__chip--" + footer.tone}>{footer.glyph} {footer.text}</span>
    </div>);
}

const ohAttributes = (face: Face) => ({
  "data-oh-card-face": face.nodeId, "data-oh-face-state": face.state, "data-oh-stage": face.raw.stage,
  "data-oh-health": face.raw.health, "data-oh-reason": face.raw.reason, "data-oh-execution": face.raw.executionId ?? "",
  "data-oh-steps-total": face.steps.total, "data-oh-steps-done": face.steps.done,
  "data-oh-lease-holder": face.lease?.holder ?? "", "data-oh-lease-epoch": face.lease?.epoch ?? "",
});

/** Celá tvář; `title` je název karty (s přejmenováním), který dodá rodič. */
export default function CardFace({ face, title }: { face: Face; title: ReactNode }) {
  return (
    <div className={"card-face card-face--" + face.state} {...ohAttributes(face)}>
      <div className="card-face__top">
        <span className="card-face__kind">{face.kindChip}</span>
        <span className="card-face__grow" />
        {face.holder && <span className={"card-face__who card-face__who--" + face.holder.who}>
          <i aria-hidden="true">{face.holder.who === "agent" ? "A" : "H"}</i>{face.holder.name}
        </span>}
      </div>
      {title}
      <div className="card-face__status" role="status">
        <span className={"card-face__chip card-face__chip--" + face.chip.tone}>{face.chip.glyph} {face.chip.word}</span>
        <span className="card-face__line">{face.stage} · {face.lease ? <LeaseCountdown expiresAt={face.lease.expiresAt} /> : face.reason}</span>
      </div>
      <div className="card-face__progress" title={`Kroky plánu ${face.steps.count}`}>
        {!!face.steps.segments.length && <div className="card-face__segments" aria-hidden="true">
          {face.steps.segments.map((segment, index) => <b key={index} className={segment ? "card-face__segment--" + segment : undefined} />)}
        </div>}
        <div className="card-face__steps"><b>{face.steps.count}</b> · {face.steps.label}</div>
      </div>
      <Footer face={face} />
    </div>
  );
}

/** Glyf pro oddálené plátno: symbol zdraví, název a tenká lišta postupu. */
export function CardGlyph({ face, name }: { face: Face; name: string }) {
  const share = face.steps.total ? face.steps.done / face.steps.total : 0;
  return (
    <div className={"card-face card-face--glyph card-face--" + face.state} {...ohAttributes(face)}
      title={`${name} · ${face.chip.word} · ${face.stage} · ${face.reason} · ${face.steps.count}`}>
      <span className={"card-face__mark card-face__mark--" + face.chip.tone} aria-label={face.chip.word}>{face.chip.glyph}</span>
      <span className="card-face__glyph-title">{name}</span>
      <span className="card-face__glyph-bar" style={{ "--share": `${Math.round(share * 100)}%` } as CSSProperties} />
    </div>
  );
}
