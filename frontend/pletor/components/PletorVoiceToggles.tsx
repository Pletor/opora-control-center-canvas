import type { VoicePrefs } from "../logic/voice-prefs";

/**
 * Dva přepínače vedle mikrofonu: Konverzace (po domluvení se mikrofon sám zapne, jinak jedna věta a konec)
 * a Hlas (odpovědi nahlas i na psané zprávy). Uložení drží rodič; bez mikrofonu Konverzace nemá smysl a chybí.
 */
export default function PletorVoiceToggles({ prefs, canListen, onChange }: { prefs: VoicePrefs; canListen: boolean; onChange: (change: Partial<VoicePrefs>) => void }) {
  return (
    <div className="pletor-mic__toggles" role="group" aria-label="Hlas Pletora">
      {canListen && (
        <label className="pletor-mic__toggle" title="Po odpovědi Pletor znovu poslouchá">
          <input type="checkbox" checked={prefs.conversation} onChange={(event) => onChange({ conversation: event.target.checked })} />
          Konverzace
        </label>
      )}
      <label className="pletor-mic__toggle" title="Odpovědi čte nahlas i na psané zprávy">
        <input type="checkbox" checked={prefs.voice} onChange={(event) => onChange({ voice: event.target.checked })} />
        Hlas
      </label>
    </div>
  );
}
