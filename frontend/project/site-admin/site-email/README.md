# E-mail (SMTP) webu

Část „E-mail (SMTP)“ ve skupině Nastavení Správy webu (`image9.png`) nad `settings.email`. Backend: `backend/project/site_admin/site_settings.py` (heslo i jakýkoli klíč `password`, `heslo`, `token`, `apiKey` je 422).

- `components/EmailSection.tsx` (rodič dílku): služba (vlastní SMTP, SendGrid, Mailgun, SES, Postmark, Resend), server, port, zabezpečení STARTTLS / TLS / bez šifrování, uživatel, **odkaz na tajemství** `secretRef` (nikdy heslo), odesílatel, jméno a reply-to. Vpravo hlavička e-mailu a rady (RFC 6409, RFC 8314). Celý e-mail hlásí `onChange`; ukládá `SiteAdmin`.
- `logic/email.ts` (+ test): tvar bez hesla, port podle zabezpečení, host známé služby, kontrola adres a `secretRef`, rady stejné jako poznámky serveru.
