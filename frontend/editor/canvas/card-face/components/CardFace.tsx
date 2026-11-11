// Tvář karty na plátně 3 (návrh „Neonový dashboard OPORA: Editor“): štítek s kódem a druhem, kdo kartu drží,
// velký název s kruhem postupu, stavová pilulka s počitadlem kroků, čtyři tečky pravd a nejvýš jedna patička.
// Pod 45 % zoomu jen glyf: kruh postupu a název.
// Všechno čte z hotové `CardFace` (agent-state) a `FaceKind` (graf); každý prvek nese `data-oh-*`, aby agent nečetl obrazovku.
import type { ReactNode } from "react";
import type { CardFace as Face } from "../logic/card-face";
import { countdown } from "../logic/face-labels";
import { useNow } from "../logic/use-now";
import { openCardDrawer } from "@/hub/oporahub-card-drawer/open";
import PrBadge from "@/shared/pr-badge/components/PrBadge";
import { FaceRing, FaceTruths } from "./FaceGrowth";
import type { FaceGrowth } from "../logic/face-growth";
import { faceCounter, facePill, type FaceKind } from "../logic/face-family";
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
      data-oh-action-id={footer.actionId} onClick={() => openCardDrawer(face.nodeId, "spec")} title={footer.text}>
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

const ohAttributes = (face: Face, growth: FaceGrowth) => ({
  "data-oh-card-face": face.nodeId, "data-oh-growth": growth.shape, "data-oh-live": growth.live ? "1" : "", "data-oh-face-state": face.state, "data-oh-stage": face.raw.stage,
  "data-oh-health": face.raw.health, "data-oh-reason": face.raw.reason, "data-oh-execution": face.raw.executionId ?? "",
  "data-oh-steps-total": face.steps.total, "data-oh-steps-done": face.steps.done,
  "data-oh-lease-holder": face.lease?.holder ?? "", "data-oh-lease-epoch": face.lease?.epoch ?? "",
  "data-oh-order": face.order ?? "",
});
const NEUTRAL: FaceKind = { family: "work", word: "Krok", code: "" };

/**
 * Celá tvář; `title` je název karty (s přejmenováním), který dodá rodič; klik na počitadlo kroků hlásí `onTrail` (boční menu se stopou práce karty).
 */
export default function CardFace({ face, growth, kind = NEUTRAL, title, onTrail }: {
  face: Face; growth: FaceGrowth; kind?: FaceKind; title: ReactNode; onTrail?: () => void;
}) {
  const pill = facePill(face);
  const counter = faceCounter(face);
  return (
    <div className={"card-face card-face--" + face.state} {...ohAttributes(face, growth)} data-oh-family={kind.family} data-oh-code={kind.code}>
      <div className="card-face__top">
        <span className={"card-face__tag card-face__tag--" + kind.family}>
          {kind.code && <b className="card-face__code">{kind.code}</b>}
          <span className="card-face__kind">{kind.word}</span>
        </span>
        <span className="card-face__grow" />
        {growth.live && <span className="card-face__live" title="Kartu drží běžící dělník" />}
        {face.holder && <span className={"card-face__who card-face__who--" + face.holder.who}>
          <i aria-hidden="true">{face.holder.who === "agent" ? "A" : "H"}</i>{face.holder.name}
        </span>}
      </div>
      <div className="card-face__row">
        <div className="card-face__name">{title}</div>
        <FaceRing growth={growth} size={34} />
      </div>
      <div className="card-face__status" role="status">
        <span className={"card-face__pill card-face__pill--" + pill.tone} data-oh-pill={pill.tone}
          title={`${face.chip.word} · ${face.stage} · ${face.reason}`}>{pill.word}</span>
        <button type="button" className="card-face__counter nodrag" data-oh-open-trail={face.nodeId}
          title={`Kroky plánu ${face.steps.count}: ${face.steps.label}. Otevřít stopu práce karty`}
          onClick={(event) => { event.stopPropagation(); onTrail?.(); }}>
          {counter || "stopa"} <span aria-hidden="true">›</span>
        </button>
        {face.lease && <LeaseCountdown expiresAt={face.lease.expiresAt} />}
      </div>
      <FaceTruths growth={growth} />
      <PrBadge badge={face.pr} />
      <Footer face={face} />
    </div>
  );
}

/** Glyf pro oddálené plátno: jen kruh postupu a název, ať plátno unese stovky karet. */
export function CardGlyph({ face, growth, name }: { face: Face; growth: FaceGrowth; name: string }) {
  return (
    <div className={"card-face card-face--glyph card-face--" + face.state} {...ohAttributes(face, growth)}
      title={`${name} · ${growth.label} · ${face.chip.word} · ${face.stage} · ${face.reason} · ${face.steps.count}${face.pr ? " · " + face.pr.label : ""}`}>
      <FaceRing growth={growth} size={48} />
      <span className="card-face__glyph-title">{name}</span>
    </div>
  );
}
