import type { EditLock } from "@/project/architecture-editor/logic/edit-locks";
import "../styles/architecture-landing.css";

/**
 * Proč jsou úpravy (např. „+ Doména“) zakázané: ukládání, načítání, chyba, uzavřená karta, obsah
 * mainu jen pro čtení. Žádné tiché zašednutí; přechodný důvod je tlumený, trvalý zlatý.
 */
export default function DomainLockNote({ lock }: { lock: EditLock }) {
  if (!lock) return null;
  return <p className={"arch-landing__lock" + (lock.transient ? " arch-landing__lock--transient" : "")} role="status" data-testid="architecture-lock-note">
    <span className="arch-landing__lock-icon" aria-hidden="true">{lock.transient ? "…" : "🔒"}</span>{lock.text}
  </p>;
}
