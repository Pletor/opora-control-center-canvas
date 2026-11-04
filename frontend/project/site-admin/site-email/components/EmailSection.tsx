import { NumberField, Segments, SelectField, TextField } from "@/project/site-admin/site-fields/components/Fields";
import { emailAdvice, emailProblem, fromHeader, readEmail, secretRefProblem, withProvider, withSecurity, type Email, type Security } from "../logic/email";
import "../styles/site-email.css";

const PROVIDERS = [{ value: "smtp", label: "Vlastní SMTP" }, { value: "sendgrid", label: "SendGrid" }, { value: "mailgun", label: "Mailgun" },
  { value: "ses", label: "Amazon SES" }, { value: "postmark", label: "Postmark" }, { value: "resend", label: "Resend" }, { value: "other", label: "Jiná služba" }];
const SECURITY = [{ value: "starttls", label: "STARTTLS (587)" }, { value: "tls", label: "TLS (465)" }, { value: "none", label: "Bez šifrování" }];

/** E-mail (SMTP) webu: služba, server, port a zabezpečení, přihlášení, odesílatel a odpovědi. Heslo se nikdy
 *  nezadává sem, jen odkaz na tajemství (`secretRef`). Vpravo hlavička e-mailu a rady. Celý e-mail hlásí nahoru. */
export default function EmailSection({ settings, onChange }: { settings: Record<string, unknown>; onChange: (email: Email) => void }) {
  const email = readEmail(settings);
  const set = (patch: Partial<Email>) => onChange({ ...email, ...patch });
  const advice = emailAdvice(email);
  return <div className="site-fields__split site-email">
    <div className="site-fields__form">
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Server</legend>
        <div className="site-fields__grid">
          <SelectField label="Služba" value={email.provider} empty={null} options={PROVIDERS} onChange={(provider) => onChange(withProvider(email, provider))}/>
          <TextField label="SMTP server" value={email.host} placeholder="smtp.example.cz" mono maxLength={253} onChange={(host) => set({ host: host.trim() })}/>
          <NumberField label="Port" value={email.port} min={1} max={65535} onChange={(port) => set({ port })}/>
          <Segments label="Zabezpečení" value={email.security} required options={SECURITY} onChange={(security) => onChange(withSecurity(email, security as Security))}/>
          <TextField label="Uživatel" value={email.username} placeholder="apikey nebo adresa" mono maxLength={320} onChange={(username) => set({ username })}/>
          <TextField label="Heslo: odkaz na tajemství" value={email.secretRef} placeholder="env:SMTP_PASSWORD" mono maxLength={217}
            hint={secretRefProblem(email.secretRef) || "Heslo patří do proměnné prostředí nebo trezoru, nikdy sem."} onChange={(secretRef) => set({ secretRef: secretRef.trim() })}/>
        </div>
      </fieldset>
      <fieldset className="site-fields__group">
        <legend className="site-fields__legend">Odesílatel</legend>
        <div className="site-fields__grid">
          <TextField label="Adresa odesílatele (from)" value={email.from} placeholder="info@example.cz" type="email" maxLength={320} hint={emailProblem(email.from) || "Doména má mít SPF, DKIM a DMARC."} onChange={(from) => set({ from: from.trim() })}/>
          <TextField label="Jméno odesílatele" value={email.fromName} placeholder="Ember" maxLength={120} onChange={(fromName) => set({ fromName })}/>
          <TextField label="Odpovědi na (reply-to)" value={email.replyTo} placeholder="podpora@example.cz" type="email" maxLength={320} hint={emailProblem(email.replyTo)} onChange={(replyTo) => set({ replyTo: replyTo.trim() })}/>
        </div>
      </fieldset>
    </div>
    <aside className="site-fields__aside site-email__preview" aria-label="Náhled e-mailu" data-testid="email-preview">
      <div className="site-email__message">
        <span className="site-email__row"><b className="site-email__key">Od</b>{fromHeader(email)}</span>
        {email.replyTo && <span className="site-email__row"><b className="site-email__key">Odpovědět</b>{email.replyTo}</span>}
        <span className="site-email__row"><b className="site-email__key">Přes</b><span><code>{email.host || "—"}:{email.port}</code> {email.security === "none" ? "bez šifrování" : email.security.toUpperCase()}</span></span>
        <span className="site-email__row"><b className="site-email__key">Heslo</b>{email.secretRef ? <code>{email.secretRef}</code> : "bez přihlášení heslem"}</span>
      </div>
      {advice.length > 0 && <ul className="site-email__advice" role="status">{advice.map((item) => <li key={item}>{item}</li>)}</ul>}
    </aside>
  </div>;
}
