import type { PanelChannel } from "../logic/assistant-prefs";

const OPTIONS: { channel: PanelChannel; label: string; hint: string }[] = [
  { channel: "heart", label: "Srdce", hint: "Kanál do srdce projektu: otázky, fronta úkolů a zprávy" },
  { channel: "assistant", label: "Asistent", hint: "Dosavadní asistent s úkoly a konverzací" },
];

/** Přepínač kanálu panelu v hlavičce: Srdce | Asistent. Jen hlásí volbu; drží a ukládá ji rodič. */
export default function ChannelSwitch({ channel, onChannel }: { channel: PanelChannel; onChannel: (channel: PanelChannel) => void }) {
  return (
    <div className="assistant-panel__channels" role="group" aria-label="Kanál panelu">
      {OPTIONS.map((o) => (
        <button
          key={o.channel}
          type="button"
          className={"assistant-panel__channel" + (o.channel === channel ? " assistant-panel__channel--on" : "")}
          aria-pressed={o.channel === channel}
          title={o.hint}
          onClick={() => onChannel(o.channel)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
