import { useState } from "react";
import { api } from "@/shared/types/logic/types";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { CLAIM_URL, identitiesUrl, identityActionUrl, identityError, parseIdentities, parseIdentity, publicIdentities, type Identity } from "../logic/identities";
import IdentityClaim from "./IdentityClaim";
import IdentityList from "./IdentityList";
import "../styles/oporahub-identity.css";

/** Lidé v review: nárok → řádek na GitHub → ověření; seznam ověřených lidí, operátor a zrušení. Jen člověk. */
export default function IdentityPanel({ project }: { project: string }) {
  const read = useHubRead(project ? identitiesUrl(project) : null, parseIdentities);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [claimed, setClaimed] = useState<Identity | null>(null);
  const items = read.data ?? [];
  async function run(work: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await work(); read.reload(); return true; } catch (failure) { setError(identityError(failure)); return false; } finally { setBusy(false); }
  }
  const forget = (identityId: string) => setClaimed(current => current?.identityId === identityId ? null : current);
  const claim = (name: string, githubLogin: string, operator: boolean) => run(async () => {
    setClaimed(parseIdentity(await api(CLAIM_URL, { project, name, githubLogin, operator })));
  });
  const verify = (identityId: string, number: number) => run(async () => {
    await api(identityActionUrl(identityId, "verify"), { project, number }); forget(identityId);
  });
  const revoke = (identityId: string) => run(async () => {
    await api(identityActionUrl(identityId, "revoke"), { project }); forget(identityId);
  });
  // Řádek k vložení: z odpovědi nároku, nebo ze seznamu (lidská session ho dostane u stavu „claimed“).
  const markerFor = (id: string) => (claimed?.identityId === id ? claimed.marker : undefined) ?? items.find(item => item.identityId === id)?.marker;
  const pending = items.filter(item => item.state === "claimed")
    .map(item => ({ identityId: item.identityId, name: item.name, githubLogin: item.githubLogin, marker: markerFor(item.identityId) }));
  return <div className="oporahub-identity" data-oh-view="identity">
    <JsonMirror id="oh-review-identities" value={{ project, items: publicIdentities(items) }} />
    <header className="oporahub-identity__head">
      <h3 className="oporahub-identity__title">Lidé v review</h3>
      <span className="oporahub-identity__note">Jen pro člověka · agent vidí jen ověřená fakta</span>
    </header>
    <p className="oporahub-identity__lead">Schválení agentem nikdy není schválení člověkem. Brána merge počítá různé ověřené lidi;
      operátor (kdo přijímá plány) se započítá jednou.</p>
    {read.error && <p className="oporahub-identity__error" role="alert">{read.error}</p>}
    {error && <p className="oporahub-identity__error" role="alert">{error}</p>}
    <IdentityClaim busy={busy} hasOperator={items.some(item => item.operator && item.state !== "revoked")} onClaim={claim}
      pending={pending} onVerify={verify} />
    <IdentityList items={items} busy={busy || read.busy} onRevoke={revoke} />
  </div>;
}
