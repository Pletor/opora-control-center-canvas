import "../styles/pletor-voice-draft.css";

type Props = { listening: boolean; draft: string; manual: boolean; endpointMs?: number; onFinish: () => void };

/** OP-5AED6F: celý rozpracovaný tah zůstává viditelný a člověk ho může dokončit sám. */
export default function PletorVoiceDraft({ listening, draft, manual, endpointMs, onFinish }: Props) {
  if (!listening) return null;
  return <section className="pletor-voice-draft" aria-label="Rozpracovaná myšlenka">
    <p className="pletor-voice-draft__cue" role="status">{manual
      ? "Poslouchám. Pauza nic neodesílá; můžeš dál přemýšlet."
      : `Poslouchám. Automaticky odešlu po ${(endpointMs ?? 8000) / 1000} sekundách ticha.`}</p>
    {manual && <p className="pletor-voice-draft__cue">Až dokončíš celou myšlenku, stiskni „Domluvil jsem“.</p>}
    {draft && <p className="pletor-voice-draft__text" aria-label="Průběžný přepis">{draft}</p>}
    {draft.trim() && <button type="button" className="pletor-voice-draft__finish" onClick={onFinish}>Domluvil jsem</button>}
  </section>;
}
