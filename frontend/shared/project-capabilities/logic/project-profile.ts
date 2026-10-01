// Profil projektu slovy: volby pro kartu profilu a Nastavení → Projekt, jména pro hlavičku šuplíku
// a krátká slova pro důvod „kvůli profilu: …“. Jen data a čisté funkce; co z profilu plyne pro
// rozhraní, rozhoduje `project-capabilities.ts`. Kontrakt: docs/suplik-a-profil.md.
import type { Architecture, Platform, Tenancy } from "@/shared/types/logic/types";
import type { ProjectProfile } from "./project-capabilities";

export type ProfileOption<T extends string> = { id: T; label: string; hint: string; word: string };

/** Architektura: jméno na volbě, věta pod ním a malé slovo do důvodu u prvku katalogu. */
export const ARCHITECTURE_OPTIONS: ProfileOption<Architecture>[] = [
  { id: "monolith", label: "Monolit", hint: "jedna aplikace, jedna databáze", word: "monolit" },
  { id: "modular", label: "Modulární monolit", hint: "jedna aplikace, moduly s hranicemi", word: "modulární monolit" },
  { id: "microservices", label: "Mikroslužby", hint: "samostatné služby, vlastní data, zprávy", word: "mikroslužby" },
  { id: "serverless", label: "Serverless", hint: "funkce a spravované služby", word: "serverless" },
];

export const TENANCY_OPTIONS: ProfileOption<Tenancy>[] = [
  { id: "single", label: "Jeden tenant", hint: "jedna firma, jedna data", word: "jeden tenant" },
  { id: "multi", label: "Multitenant", hint: "víc zákazníků, oddělená data", word: "multitenant" },
];

export const PLATFORM_LABELS: Record<Platform, string> = { web: "Web", app: "Aplikace", component: "Komponenta" };

export const architectureWord = (value: Architecture): string =>
  ARCHITECTURE_OPTIONS.find((option) => option.id === value)?.word ?? value;
export const tenancyWord = (value: Tenancy): string =>
  TENANCY_OPTIONS.find((option) => option.id === value)?.word ?? value;

/** Hlavička šuplíku: „Web · Modulární monolit · Multitenant“; nenastavený profil to řekne slovy. */
export function profileWords(profile: ProjectProfile): string {
  const parts = [
    PLATFORM_LABELS[profile.platform],
    ARCHITECTURE_OPTIONS.find((option) => option.id === profile.architecture)?.label,
    TENANCY_OPTIONS.find((option) => option.id === profile.tenancy)?.label,
  ].filter(Boolean);
  if (!profile.architecture && !profile.tenancy) parts.push("profil nenastaven");
  return parts.join(" · ");
}
