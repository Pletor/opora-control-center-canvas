import { useCallback, useEffect, useRef, useState } from "react";
import AssistantInstructionsSetting from "@/settings/components/AssistantInstructionsSetting";
import JevKeySetting from "@/settings/components/JevKeySetting";
import { instructionsPayload, parseAssistantInstructions, type AssistantInstructions } from "@/settings/logic/assistant-instructions";
import { api } from "@/shared/types/logic/types";

const URL = "/api/assistant/instructions";

/**
 * Asistent: pokyny s váhou systémového promptu (na serveru, pro celou aplikaci). Sekce je načte
 * při otevření, drží rozepsaný text a po uložení nebo obnovení znovu čte odpověď serveru.
 */
export default function AssistantSection() {
  const [config, setConfig] = useState<AssistantInstructions | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const generation = useRef(0);

  const read = useCallback(async () => {
    const ticket = ++generation.current;
    try {
      const value = parseAssistantInstructions(await api<unknown>(URL));
      if (ticket !== generation.current) return;
      setConfig(value);
      if (value) setDraft(value.text);
      setError(value ? "" : "Server vrátil neznámý tvar pokynů asistenta.");
    } catch (reason) {
      if (ticket !== generation.current) return;
      setConfig(null);
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    void read();
    return () => { ++generation.current; };
  }, [read]);

  async function write(text: string | null) {
    if (saving) return;
    setSaving(true);
    try {
      await api<AssistantInstructions>(URL, instructionsPayload(text));
      await read();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="settings-section" aria-labelledby="assistant-title">
      <h3 id="assistant-title">Asistent</h3>
      <p className="muted">Pokyny mají váhu systémového promptu a platí pro celou aplikaci. Projeví se v nové session.</p>
      <AssistantInstructionsSetting
        config={config}
        draft={draft}
        saving={saving}
        error={error}
        onDraftChange={setDraft}
        onSave={() => void write(draft)}
        onReset={() => void write(null)}
      />
      <JevKeySetting />
    </section>
  );
}
