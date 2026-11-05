import { readVoicePrefs } from "@/agi-pletor/hud/logic/voice-prefs";
import { isCloud, voiceGroups, voiceTitle } from "@/agi-pletor/hud/logic/tts-voices";
import { voiceName } from "../logic/overview-cards";
import { useVoiceList } from "../logic/use-voice-list";

/**
 * Hlas (V1, jen čtení): hlasy serveru po enginech a ten, kterým Pletor čte teď. Výběr a „Vyzkoušet“ drží hook
 * `usePletorVoice` uvnitř okna Pletora; z velínu se k němu nedá sáhnout, proto výběr zůstává v kokpitu (dluh V1).
 */
export default function DashboardVoice() {
  const voices = useVoiceList();
  if (!voices) return <p className="pletor-dashboard__note" role="status">Načítám hlasy…</p>;
  const current = voiceName(readVoicePrefs().ttsVoice, voices);
  return (
    <>
      <p className="pletor-dashboard__note">Čte se hlasem: <b>{current}</b>. Výběr hlasu zatím v kokpitu (ozubené kolo).</p>
      {voiceGroups(voices).map((group) => (
        <section key={group.id} className="pletor-dashboard__group" aria-label={group.label}>
          <h2 className="pletor-dashboard__group-title">{group.label}</h2>
          <ul className="pletor-dashboard__voices">
            {group.voices.map((voice) => (
              <li key={voice.id} className="pletor-dashboard__voice" title={voiceTitle(voice)}>
                <span className="pletor-dashboard__voice-name">{voice.label}</span>
                <span className="pletor-dashboard__voice-tag">{isCloud(voice.engine) ? "cloud" : "lokální"}</span>
                {!voice.available && <span className="pletor-dashboard__voice-off">{voice.reason || "nedostupný"}</span>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
