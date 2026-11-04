import type { ReactNode } from "react";
import { designSummary, type DesignTokens, type ScaleKind, type SiteDocument } from "../logic/site-document";
import { siteAdminUrls, type SiteInvalid } from "../logic/site-admin-api";
import { tokenNames } from "../logic/token-names";
import { siteMenuItem, type SiteSection } from "../site-menu/logic/site-sections";
import OverviewSection from "../ds-overview/components/OverviewSection";
import ColorsSection from "../ds-colors/components/ColorsSection";
import TypographySection from "../ds-typography/components/TypographySection";
import { fontFromUpload } from "../ds-typography/logic/typography";
import ScaleSection from "../ds-scale/components/ScaleSection";
import FilesSection from "../ds-files/components/FilesSection";
import AppearanceSection from "../site-appearance/components/AppearanceSection";
import { imageAssets } from "../site-appearance/logic/appearance";
import ButtonsSection from "../site-buttons/components/ButtonsSection";
import { readButtons } from "../site-buttons/logic/button-model";
import SeoSection from "../site-seo/components/SeoSection";
import { readSeo } from "../site-seo/logic/seo";
import AffiliateSection from "../site-affiliate/components/AffiliateSection";
import EmailSection from "../site-email/components/EmailSection";
import HeaderSection from "../site-header/components/HeaderSection";
import FooterSection from "../site-footer/components/FooterSection";
import CookieBarSection from "../site-cookie-bar/components/CookieBarSection";
import { readGdpr } from "../site-cookie-bar/logic/cookie-bar";

const LEAD: Partial<Record<SiteSection, string>> = {
  seo: "Jak web najdou vyhledávače a jak vypadá sdílený odkaz: šablona titulku, popis, indexování, Open Graph a strukturovaná data. Stránka smí mít vlastní titulek a popis.",
  affiliate: "Partnerský program webu: parametr v odkazu, jak dlouho si web partnera pamatuje a komu patří provize.",
  email: "Odkud web posílá e-maily (formuláře, objednávky). Heslo se sem nikdy nepíše, jen odkaz na tajemství.",
  header: "Hlavička na každé stránce webu: logo, menu a tlačítko výzvy. Menu se skládá ze stránek mapy domény, nebo ručně.",
  footer: "Patička na každé stránce webu: sloupce odkazů, sociální sítě, právní řádek a odkaz na nastavení cookies.",
  cookies: "Cookie lišta podle GDPR a ePrivacy: odmítnout stejně snadno jako přijmout, nic předem zaškrtnutého, souhlas jde kdykoli změnit.",
  appearance: "Jak vypadá každá stránka webu: pozadí, písmo, barvy textu a odkazů, nadpisy, odrážky a šířka. Každé pole zapisuje token design systému.",
  buttons: "Varianty tlačítek se stavy, barevným přechodem a vlastním CSS s animací. AI je používá třídou ds-btn ds-btn--<varianta>.",
  overview: "Jméno systému, co obsahuje a brand book. README je první, co čte AI při každém vývoji webu.",
  colors: "Barvy pro každé téma. Hodnota je barva nebo alias jiné barvy; odznak říká, jestli text projde kontrastem WCAG.",
  typography: "Rodiny písma, vlastní fonty a typografické styly. Ukázka ukazuje styl tak, jak ho uvidí web.",
  fonts: "Vlastní fonty webu jsou součást typografie design systému.",
  spacing: "Škála mezer, ze které web skládá rytmus. Číslo je v pixelech.",
  radius: "Zaoblení rohů tlačítek, karet a polí.",
  shadow: "Stíny podle úrovně elevace; každé téma může mít vlastní.",
  files: "Odvozené soubory, které dostane dělník do design/.",
};

/** Co panel potřebuje od rodiče: rozepsaný dokument, jak ho změnit, téma náhledu a stav nahrávání fontu. */
export type SitePanelContext = {
  project: string; document: SiteDocument; revision: number; dirty: boolean; theme: string;
  componentsCss: string; notes: string[]; invalid: SiteInvalid | null;
  uploading: boolean; uploadError: string;
  change: (update: (document: SiteDocument) => SiteDocument) => void;
  upload: (file: File, record: (path: string) => (document: SiteDocument) => SiteDocument) => void;
  onSelect: (section: SiteSection) => void;
};

const withSettings = (document: SiteDocument, settings: Record<string, unknown>): SiteDocument =>
  ({ ...document, settings: { ...document.settings, ...settings } });

const withTokens = (document: SiteDocument, key: string, value: DesignTokens[string]): SiteDocument =>
  ({ ...document, design: { ...document.design, tokens: { ...document.design.tokens, [key]: value } as DesignTokens } });

function editor(section: SiteSection, context: SitePanelContext): ReactNode {
  const { document, change } = context;
  const tokens = document.design.tokens;
  const themes = tokens.color.themes;
  const taken = tokenNames(tokens);
  switch (section) {
    case "overview": return <OverviewSection title={document.title} readme={document.design.readme} summary={designSummary(document.design)}
      onTitle={(title) => change((current) => ({ ...current, title }))} onReadme={(readme) => change((current) => ({ ...current, design: { ...current.design, readme } }))}
      onOpen={context.onSelect}/>;
    case "colors": return <ColorsSection family={tokens.color} taken={taken} onChange={(color) => change((current) => withTokens(current, "color", color))}/>;
    case "typography": case "fonts": return <TypographySection type={tokens.type} theme={context.theme} uploading={context.uploading} uploadError={context.uploadError}
      onChange={(type) => change((current) => withTokens(current, "type", type))}
      onUploadFont={(file) => context.upload(file, (path) => (current) => withTokens(current, "type", { ...current.design.tokens.type, fonts: [...current.design.tokens.type.fonts, fontFromUpload(file.name, path)] }))}/>;
    case "spacing": case "radius": case "shadow": {
      const kind: ScaleKind = section;
      return <ScaleSection kind={kind} family={tokens[kind]} themes={themes} taken={taken} onChange={(family) => change((current) => withTokens(current, kind, family))}/>;
    }
    case "files": return <FilesSection revision={context.revision} dirty={context.dirty} urls={{
      "tokens.css": siteAdminUrls.file(context.project, "tokens.css"), "components.css": siteAdminUrls.file(context.project, "components.css"), "tokens.json": siteAdminUrls.file(context.project, "tokens.json"),
      "README.md": siteAdminUrls.file(context.project, "README.md") }}/>;
    case "appearance": return <AppearanceSection settings={document.settings} project={context.project} theme={context.theme}
      aliases={tokens.color.tokens.map((token) => token.name)} stacks={Object.values(tokens.type.families)} assets={imageAssets(document.design.assetGroups)}
      onChange={(appearance) => change((current) => withSettings(current, { appearance }))}/>;
    case "buttons": return <ButtonsSection settings={document.settings} project={context.project} theme={context.theme} componentsCss={context.componentsCss}
      notes={context.notes} invalid={context.invalid} aliases={tokens.color.tokens.map((token) => token.name)} families={Object.keys(tokens.type.families)}
      onChange={({ buttons, customCss }) => change((current) => withSettings(current, { buttons, customCss: { button: customCss } }))}/>;
    case "seo": return <SeoSection settings={document.settings} project={context.project} assets={imageAssets(document.design.assetGroups)}
      onChange={(seo) => change((current) => withSettings(current, { seo }))}/>;
    case "affiliate": return <AffiliateSection settings={document.settings} host={readSeo(document.settings).canonicalHost}
      marketing={readGdpr(document.settings).cookieBar.categories.includes("marketing")} onChange={(affiliate) => change((current) => withSettings(current, { affiliate }))}/>;
    case "email": return <EmailSection settings={document.settings} onChange={(email) => change((current) => withSettings(current, { email }))}/>;
    case "header": return <HeaderSection settings={document.settings} project={context.project} theme={context.theme} componentsCss={context.componentsCss}
      assets={imageAssets(document.design.assetGroups)} variants={Object.keys(readButtons(document.settings).variants)} onChange={(header) => change((current) => withSettings(current, { header }))}/>;
    case "footer": return <FooterSection settings={document.settings} project={context.project} theme={context.theme} componentsCss={context.componentsCss}
      onChange={(footer) => change((current) => withSettings(current, { footer }))}/>;
    case "cookies": return <CookieBarSection settings={document.settings} project={context.project} theme={context.theme} componentsCss={context.componentsCss}
      onChange={(gdpr) => change((current) => withSettings(current, { gdpr }))}/>;
    // Sloty pro další PR (Components, Assets): editor přidá svůj `case` a v `site-sections.ts` přepne `ready`.
    default: return null;
  }
}

/** Obsah vybrané části: nadpis, jedna věta, k čemu je, a editor. Část bez editoru řekne, že přijde v dalším kroku. */
export default function SitePanel({ section, context }: { section: SiteSection; context: SitePanelContext }) {
  const entry = siteMenuItem(section);
  const body = entry.ready ? editor(section, context) : null;
  return <section className="site-admin__panel" aria-label={entry.label} data-testid={"site-panel-" + section}>
    <header className="site-admin__panel-head">
      <h2 className="site-admin__panel-title">{entry.label}</h2>
      {LEAD[section] && <p className="site-admin__panel-lead">{LEAD[section]}</p>}
    </header>
    {body ?? <p className="site-admin__later" role="status">Tahle část přijde v dalším kroku. Teď je hotové Nastavení (SEO, Affiliate, E-mail), Vzhled (hlavička, patička, tlačítka, fonty), Cookie lišta a Design System: Overview, Colors, Typography, Spacing, Corner radius, Shadows a Files.</p>}
  </section>;
}
