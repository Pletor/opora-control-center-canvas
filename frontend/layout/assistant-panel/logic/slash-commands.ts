/**
 * Lomítkové příkazy, které model sám nespustí (`disable-model-invocation`), takže je uživatel píše
 * do pole. Nápověda se ukáže, dokud pole začíná `/` a uživatel ještě píše jméno příkazu.
 */
export type SlashCommand = { name: string; hint: string };

export const SLASH_COMMANDS: SlashCommand[] = [
  { name: "/grill-me", hint: "vyzpovídá vás k nápadu a zpřesní jádro zadání" },
  { name: "/wayfinder", hint: "velké zadání v mlze rozloží na sektor a karty" },
];

export function slashHints(text: string): SlashCommand[] {
  if (!text.startsWith("/") || /\s/.test(text)) return [];
  const typed = text.toLowerCase();
  return SLASH_COMMANDS.filter((c) => c.name.startsWith(typed) && c.name !== typed);
}
