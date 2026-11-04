import { expect, it } from "vitest";
import { EMPTY_EMAIL, emailAdvice, emailProblem, fromHeader, readEmail, secretRefProblem, withProvider, withSecurity } from "./email";

it("reads email with defaults and never carries a password field", () => {
  expect(readEmail({})).toEqual(EMPTY_EMAIL);
  const read = readEmail({ email: { host: "smtp.x.cz", password: "hunter2", security: "ssl" } });
  expect(read.host).toBe("smtp.x.cz");
  expect(read.security).toBe("starttls");
  expect("password" in read).toBe(false);
});

it("switches port with security only when it was the default", () => {
  expect(withSecurity(EMPTY_EMAIL, "tls").port).toBe(465);
  expect(withSecurity({ ...EMPTY_EMAIL, port: 2525 }, "tls").port).toBe(2525);
});

it("fills the host of a known provider", () => {
  expect(withProvider(EMPTY_EMAIL, "sendgrid").host).toBe("smtp.sendgrid.net");
  expect(withProvider({ ...EMPTY_EMAIL, host: "smtp.sendgrid.net" }, "mailgun").host).toBe("smtp.mailgun.org");
  expect(withProvider({ ...EMPTY_EMAIL, host: "mail.ember.cz" }, "sendgrid").host).toBe("mail.ember.cz");
});

it("checks addresses, secret refs and gives the server's advice", () => {
  expect(emailProblem("x")).not.toBe("");
  expect(emailProblem("kavarna@ember.cz")).toBe("");
  expect(secretRefProblem("hunter2")).not.toBe("");
  expect(secretRefProblem("env:SMTP_PASSWORD")).toBe("");
  expect(emailAdvice({ ...EMPTY_EMAIL, host: "h", port: 465 }).join()).toMatch("RFC 8314");
  expect(emailAdvice({ ...EMPTY_EMAIL, host: "h", security: "none", from: "a@b.cz", secretRef: "env:X" })).toHaveLength(1);
  expect(fromHeader({ ...EMPTY_EMAIL, from: "a@b.cz", fromName: "Ember" })).toBe("Ember <a@b.cz>");
});
