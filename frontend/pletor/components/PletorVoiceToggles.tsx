import { BROWSER_VOICE, type PiperVoice } from "../logic/tts-piper";
import type { VoicePrefs } from "../logic/voice-prefs";

/**
 * Dva přepínače vedle mikrofonu: Konverzace (po domluvení se mikrofon sám zapne, jinak jedna věta a konec)
 * a Hlas (odpovědi nahlas i na psané zprávy). Pod nimi volba hlasu (P3b): stažené hlasy Piperu a Prohlížeč;
 * `chosen` je hlas, kterým se skutečně čte (`null` = prohlížeč). Uložení drží rodič; bez mikrofonu Konverzace chybí.
 */
export default function PletorVoiceToggles({ prefs, canListen, voices, chosen, onChange }: {
  prefs: VoicePrefs; canListen: boolean; voices: PiperVoice[]; chosen: string | null; onChange: (change: Partial<VoicePrefs>) => void;
}) {
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
      <select className="pletor-mic__voice" aria-label="Kterým hlasem Pletor čte" title="Kterým hlasem Pletor čte"
        value={chosen ?? BROWSER_VOICE} onChange={(event) => onChange({ ttsVoice: event.target.value })}>
        {voices.map((voice) => <option key={voice.id} value={voice.id}>{voice.label}</option>)}
        <option value={BROWSER_VOICE}>Prohlížeč</option>
      </select>
    </div>
  );
}
