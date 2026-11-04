import { BROWSER_VOICE, voiceGroups, voiceLabel, voiceTitle, type ServerVoice } from "../logic/tts-voices";
import type { VoicePrefs } from "../logic/voice-prefs";

/**
 * Dva přepínače vedle mikrofonu: Konverzace (po domluvení se mikrofon sám zapne, jinak jedna věta a konec)
 * a Hlas (odpovědi nahlas i na psané zprávy). Pod nimi volba hlasu seskupená podle enginu (XTTS, ElevenLabs, Edge,
 * Piper, Prohlížeč); nedostupný hlas je vidět, ale nejde zvolit, a důvod ukáže tooltip; ElevenLabs ukazuje zbývající znaky. `chosen` je hlas, kterým se
 * skutečně čte (`null` = prohlížeč). Uložení drží rodič; bez mikrofonu Konverzace chybí.
 */
export default function PletorVoiceToggles({ prefs, canListen, voices, chosen, onChange }: {
  prefs: VoicePrefs; canListen: boolean; voices: ServerVoice[]; chosen: string | null; onChange: (change: Partial<VoicePrefs>) => void;
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
        {voiceGroups(voices).map((group) => (
          <optgroup key={group.id} label={group.label}>
            {group.voices.map((voice) => (
              <option key={voice.id} value={voice.id} disabled={!voice.available} title={voiceTitle(voice)}>
                {voiceLabel(voice)}
              </option>
            ))}
          </optgroup>
        ))}
        <optgroup label="Prohlížeč">
          <option value={BROWSER_VOICE}>Prohlížeč</option>
        </optgroup>
      </select>
    </div>
  );
}
