import { createContext, useContext, type ReactNode } from "react";
import { useSaveParticipant, type SaveParticipant } from "@/shared/hooks/logic/save-coordinator";

/** Scope metadata only; each editor keeps ownership of its draft and save operation. */
const SaveScope = createContext<{ project: string; workspace: string } | null>(null);

export function SaveScopeProvider({ project, workspace, children }: {
  project: string; workspace: string; children: ReactNode;
}) {
  return <SaveScope.Provider value={{ project, workspace }}>{children}</SaveScope.Provider>;
}

export function useScopedSaveParticipant(value: Omit<SaveParticipant, "project" | "workspace">) {
  const scope = useContext(SaveScope);
  useSaveParticipant({ ...value, id: JSON.stringify([scope?.project, scope?.workspace, value.id]),
    project: scope?.project ?? "", workspace: scope?.workspace ?? "", dirty: !!scope && value.dirty });
}

/** A swallowed parent error must never turn an unchanged form into a saved checkpoint. */
export async function confirmSavedChange(operation: () => unknown, stillDirty: () => boolean) {
  const result = await operation();
  if (result === false) throw new Error("Změnu se nepodařilo uložit. Koncept zůstává ve formuláři.");
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
  if (stillDirty()) throw new Error("Server zatím nepotvrdil změnu. Zkontrolujte chybu ve formuláři a zkuste uložení znovu.");
}
