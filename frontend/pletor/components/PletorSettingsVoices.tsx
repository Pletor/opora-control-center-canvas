import { BROWSER_VOICE, isCloud, voiceGroups, voiceTitle, type ServerVoice } from "../logic/tts-voices";

type Row = { id: string; label: string; cloud: boolean; available: boolean; reason: string | null; title?: string };
type Props = { voices: ServerVoice[]; chosen: string | null; onChoose: (id: string) => void; onTry: (id: string) => void };

/**
 * Tabulka hlasů v nastavení Pletora, po skupinách enginů (XTTS, ElevenLabs, Edge, Piper, Prohlížeč). U hlasu jméno,
 * štítek cloud / lokální a u nedostupného důvod; zbývající znaky ElevenLabs nese popisek skupiny (`voiceGroups`).
 * Klik na řádek hlas zvolí (`chosen` = čím se skutečně čte, `null` = prohlížeč), „Vyzkoušet“ přečte krátkou větu.
 */
export default function PletorSettingsVoices({ voices, chosen, onChoose, onTry }: Props) {
  const groups = [
    ...voiceGroups(voices).map((group) => ({
      id: group.id, label: group.label,
      rows: group.voices.map((voice): Row => ({ id: voice.id, label: voice.label, cloud: isCloud(voice.engine), available: voice.available, reason: voice.reason, title: voiceTitle(voice) })),
    })),
    { id: BROWSER_VOICE, label: "Prohlížeč · záloha", rows: [{ id: BROWSER_VOICE, label: "Prohlížeč", cloud: false, available: true, reason: null } as Row] },
  ];
  const selected = chosen ?? BROWSER_VOICE;
  return (
    <div className="pletor-settings__voices" role="radiogroup" aria-label="Kterým hlasem Pletor čte">
      {groups.map((group) => (
        <section key={group.id} className="pletor-settings__group" aria-label={group.label}>
          <h4 className="pletor-settings__group-title">{group.label}</h4>
          {group.rows.map((row) => (
            <div key={row.id} className={"pletor-settings__voice" + (row.id === selected ? " pletor-settings__voice--chosen" : "")}>
              <button type="button" role="radio" aria-checked={row.id === selected} className="pletor-settings__voice-pick"
                disabled={!row.available} title={row.title} onClick={() => onChoose(row.id)}>
                <span className="pletor-settings__voice-name">{row.label}</span>
                <span className={`pletor-settings__badge pletor-settings__badge--${row.cloud ? "cloud" : "local"}`}>{row.cloud ? "cloud" : "lokální"}</span>
                {!row.available && <span className="pletor-settings__reason">{row.reason || "nedostupný"}</span>}
              </button>
              <button type="button" className="pletor-settings__try" disabled={!row.available} onClick={() => onTry(row.id)}
                aria-label={`Vyzkoušet hlas ${row.label}`}>Vyzkoušet</button>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
