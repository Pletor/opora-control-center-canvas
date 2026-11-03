import type { DomainKind } from "../logic/domain-kind";

/** Small outline icon for the domain kind: globe (web), window (application), gear (administration),
 *  a phone with the Android antennae or with the iPhone notch (mobile applications). */
export default function DomainKindIcon({ kind }: { kind: DomainKind }) {
  return <svg className={"arch-landing__icon arch-landing__icon--" + kind} viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
    {kind === "web" && <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.2"/></>}
    {kind === "app" && <><rect x="3.5" y="3.5" width="17" height="17" rx="3"/><rect x="8.5" y="8.5" width="7" height="7" rx="1"/></>}
    {kind === "android" && <><rect x="6" y="6" width="12" height="15" rx="2.5"/><path d="M9 6 7.5 3.5M15 6l1.5-2.5"/><circle cx="10" cy="10" r=".6"/><circle cx="14" cy="10" r=".6"/></>}
    {kind === "ios" && <><rect x="6.5" y="2.5" width="11" height="19" rx="3"/><path d="M10.5 5h3M11 18.5h2"/></>}
    {kind === "admin" && <><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/></>}
  </svg>;
}
