import "../styles/pletor-voice-draft.css";

type Props = { listening: boolean; draft: string; manual: boolean; onFinish: () => void };

/** OP-5AED6F: celý rozpracovaný tah zůstává viditelný a člověk ho může dokončit sám. */
export default function PletorVoiceDraft({ listening, draft, manual, onFinish }: Props) {
  if (!listening) return null;
  return <section className="pletor-voice-draft" aria-label="Rozpracovaná myšlenka">
    <p className="pletor-voice-draft__cue" role="status">Poslouchám. Máš čas dokončit myšlenku.</p>
    {manual && <p className="pletor-voice-draft__cue">Odešlu až po stisknutí „Domluvil jsem“.</p>}
    {draft && <p className="pletor-voice-draft__text" aria-label="Průběžný přepis">{draft}</p>}
    {draft.trim() && <button type="button" className="pletor-voice-draft__finish" onClick={onFinish}>Domluvil jsem</button>}
  </section>;
}
