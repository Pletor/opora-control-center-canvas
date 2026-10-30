import { useState } from "react";
import type { CloseCardModel } from "../logic/close-card";
import "../styles/close-card.css";

type Props = {
  model: CloseCardModel | null;
  /** Zápis `done` přes rodiče (App, desktop-state se zámkem a revizí); vrací chybu nebo "". `null` = bez Editoru. */
  onCloseCard: ((note: string) => Promise<string>) | null;
  readOnly: boolean;
};

/** Pruh nad patičkou detailu: po sloučení PR člověk kartu uzavře jedním tlačítkem, nebo vidí, co ještě chybí. */
export default function CloseCardPanel({ model, onCloseCard, readOnly }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  if (!model) return null;
  if (model.state === "blocked")
    return <div className="close-card close-card--blocked" data-oh-close-card="blocked" data-oh-block-reason={model.blockReason}>
      <p className="close-card__reason">{model.reason}</p>
    </div>;
  const unavailable = !onCloseCard || readOnly;
  async function submit() {
    if (!onCloseCard || !model || model.state !== "ready") return;
    setPending(true); setError("");
    const failure = await onCloseCard(model.note);
    setPending(false); setError(failure);
  }
  return <div className="close-card close-card--ready" data-oh-close-card="ready" data-oh-merge-sha={model.mergeSha} data-oh-execution={model.executionId}>
    <div className="close-card__text">
      <b className="close-card__title">PR je sloučený, kartu uzavírá člověk</b>
      <span className="close-card__merge">{model.mergeText}</span>
      {unavailable && <span className="close-card__hint">Uzavřít jde jen v Editoru s právem zápisu.</span>}
      {error && <span className="close-card__error" role="alert">{error}</span>}
    </div>
    <button type="button" className="close-card__button" disabled={unavailable || pending} onClick={submit}>
      {pending ? "Uzavírám…" : model.label}
    </button>
  </div>;
}
