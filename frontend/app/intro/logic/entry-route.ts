/** Explicit workspace links keep their destination; an unqualified visit opens the entry. */
export function showsIntro(search: string): boolean {
  const query = new URLSearchParams(search);
  if (query.has("screen")) return query.get("screen") === "intro";
  return !["project", "workspace", "mode", "layer", "environment", "env", "projectView"].some((key) => query.has(key));
}

export const ENTRY_LINKS = [
  { id: "pletor", number: "01", title: "Pletor", label: "Začněme myšlenkou", description: "Prostor pro váš směr, otázky a nové nápady.", href: "/?screen=home&entry=pletor", action: "Otevřít konverzaci" },
  { id: "settings", number: "02", title: "Nastavení", label: "Zázemí pro spolupráci", description: "Nastavení Opory, dostupné skills a propojení.", href: "/?screen=settings", action: "Otevřít nastavení" },
  { id: "projects", number: "03", title: "Projekty", label: "Od vize k aplikaci", description: "Vaše repozitáře, design systémy a pracovní plátna.", href: "/?screen=home", action: "Otevřít projekty" },
] as const;
