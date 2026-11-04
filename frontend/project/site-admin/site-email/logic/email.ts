// E-mail webu `settings.email` (backend `backend/project/site_admin/site_settings.py`): odesílání přes SMTP nebo
// službu. Heslo do dokumentu nikdy nepatří, jen odkaz `secretRef` (`env:SMTP_PASSWORD`) na tajemství mimo repo.
// Porty podle RFC: 587 submission se STARTTLS (RFC 6409), 465 implicitní TLS (RFC 8314), 25 jen mezi servery.
import { readPart } from "@/project/site-admin/site-fields/logic/settings-part";

export type Security = "starttls" | "tls" | "none";
export type Email = {
  provider: string; host: string; port: number; security: Security; username: string;
  from: string; fromName: string; replyTo: string; secretRef: string;
};

export const EMPTY_EMAIL: Email = { provider: "smtp", host: "", port: 587, security: "starttls", username: "", from: "", fromName: "", replyTo: "", secretRef: "" };
export const PORT_FOR: Record<Security, number> = { starttls: 587, tls: 465, none: 25 };

/** Hostitel SMTP známých služeb, aby ho člověk nemusel hledat. */
export const PROVIDER_HOST: Record<string, string> = {
  smtp: "", sendgrid: "smtp.sendgrid.net", mailgun: "smtp.mailgun.org", ses: "email-smtp.eu-central-1.amazonaws.com",
  postmark: "smtp.postmarkapp.com", resend: "smtp.resend.com", other: "",
};

export const readEmail = (settings: Record<string, unknown>): Email => {
  const email = readPart(settings, "email", EMPTY_EMAIL);
  return { ...email, security: (["starttls", "tls", "none"] as Security[]).includes(email.security) ? email.security : "starttls" };
};

/** Změna zabezpečení: port se přepne na výchozí jen tehdy, když byl výchozí pro předchozí režim. */
export function withSecurity(email: Email, security: Security): Email {
  const port = email.port === PORT_FOR[email.security] ? PORT_FOR[security] : email.port;
  return { ...email, security, port };
}

/** Změna služby: host se doplní, když byl prázdný nebo patřil jiné známé službě. */
export function withProvider(email: Email, provider: string): Email {
  const known = Object.values(PROVIDER_HOST).includes(email.host);
  return { ...email, provider, host: !email.host || known ? PROVIDER_HOST[provider] ?? email.host : email.host };
}

const EMAIL = /^[^\s@<>"(),;:]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$/;
const SECRET_REF = /^[A-Za-z][A-Za-z0-9_-]{0,15}:[A-Za-z0-9_./-]{1,200}$/;
export const emailProblem = (value: string): string => !value.trim() || EMAIL.test(value.trim()) ? "" : "Adresa ve tvaru jmeno@domena.cz.";
export const secretRefProblem = (value: string): string =>
  !value.trim() || SECRET_REF.test(value.trim()) ? "" : "Odkaz na tajemství ve tvaru env:SMTP_PASSWORD, ne heslo samotné.";

/** Rady k nastavení (stejné jako poznámky serveru). */
export function emailAdvice(email: Email): string[] {
  const out: string[] = [];
  if (email.port === 465 && email.security === "starttls") out.push("Port 465 čeká implicitní TLS (RFC 8314), ne STARTTLS.");
  if (email.port === 587 && email.security === "tls") out.push("Port 587 je submission se STARTTLS (RFC 6409); implicitní TLS běží na 465.");
  if (email.host && email.security === "none") out.push("Spojení bez šifrování: přihlašovací údaje i pošta půjdou čitelně.");
  if (email.host && !email.from) out.push("Chybí adresa odesílatele.");
  if (email.host && !email.secretRef) out.push("Bez secretRef se server přihlásí bez hesla (jen u relé v síti).");
  return out;
}

/** Hlavička odeslaného e-mailu: `Jméno <adresa>`. */
export const fromHeader = (email: Email): string => email.fromName ? `${email.fromName} <${email.from || "…"}>` : email.from || "…";
