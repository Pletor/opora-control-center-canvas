/**
 * Pokyny asistenta = systémový prompt (docs/asistent.md §14.1).
 *
 * Platí pro celou aplikaci, nikdy pro jeden projekt. Čtou se z `GET /api/assistant/instructions`
 * a mění přes `POST /api/assistant/instructions {text}`; `text: null` obnoví výchozí. Změna platí
 * pro nově spuštěnou session.
 */
export const INSTRUCTIONS_LIMIT = 12000;

export type AssistantInstructions = { text: string; isDefault: boolean; defaultText: string };

/** Co ukáže dílek pod polem. */
export type InstructionsView = {
  chars: number;
  overLimit: boolean;
  /** Text v poli se liší od uloženého. */
  dirty: boolean;
  detail: string;
};

/** Odpověď serveru; cizí tvar se čte jako „neznámý stav“. */
export function parseAssistantInstructions(value: unknown): AssistantInstructions | null {
  if (!value || typeof value !== "object") return null;
  const { text, isDefault, defaultText } = value as { text?: unknown; isDefault?: unknown; defaultText?: unknown };
  if (typeof text !== "string" || typeof isDefault !== "boolean" || typeof defaultText !== "string") return null;
  return { text, isDefault, defaultText };
}

/** Tělo POST; `null` = obnovit výchozí. */
export function instructionsPayload(text: string | null): { text: string | null } {
  return { text };
}

export function instructionsView(config: AssistantInstructions | null, draft: string): InstructionsView {
  const chars = draft.length;
  const overLimit = chars > INSTRUCTIONS_LIMIT;
  if (!config) return { chars, overLimit, dirty: false, detail: "Zjišťuji pokyny asistenta…" };
  return {
    chars,
    overLimit,
    dirty: draft !== config.text,
    detail: config.isDefault ? "Výchozí text z aplikace." : "Vlastní text, platí pro nové session.",
  };
}
