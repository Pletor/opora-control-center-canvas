"""Sekce „Nastavení webu“ generovaného README (`compile.readme`): co má dělník na webu dodržet a jakým markupem.

Píše jen to, co je nastavené; heslo SMTP nikdy (jen `secretRef`). Zdroj pravdy je dokument Správy webu.
"""


def _target(link):
    return f"stránka `{link['pageId']}`" if link.get("pageId") else f"`{link.get('url')}`"


def _links(links):
    return ", ".join(f"{item['label']} → {_target(item)}" for item in links)


def _robots(robots):
    out = ["index" if robots["index"] else "noindex", "follow" if robots["follow"] else "nofollow"]
    out += [key for key in ("noarchive", "nosnippet") if robots[key]]
    out += [f"max-image-preview:{robots['maxImagePreview']}", f"max-snippet:{robots['maxSnippet']}"]
    return ", ".join(out)


def _seo(seo):
    out = ["#### SEO", "",
           f"- `<title>`: šablona `{seo['titleTemplate']}` (`%s` = titulek stránky)"
           + (f", web `{seo['siteName']}`" if seo["siteName"] else "") + ".",
           f"- `<html lang>` a `og:locale`: `{seo['locale']}`. Robots: `{_robots(seo['robots'])}`."]
    if seo["description"]:
        out.append(f"- Výchozí meta description: „{seo['description']}“ (stránka smí mít vlastní).")
    if seo["canonicalHost"]:
        out.append(f"- `<link rel=\"canonical\">` vždy na `https://{seo['canonicalHost']}` + cesta stránky.")
    out.append(f"- Open Graph `og:type` `{seo['ogType']}`, `og:title`, `og:description`, `og:url`"
               + (f", `og:image` `{seo['ogImage']}`" if seo["ogImage"] else "")
               + f"; `twitter:card` `{seo['twitterCard']}`"
               + (f", `twitter:site` `{seo['twitterSite']}`" if seo["twitterSite"] else "") + ".")
    out.append("- `sitemap.xml` a odkaz na něj v `robots.txt`." if seo["sitemap"] else "- Bez `sitemap.xml`.")
    if seo["structuredData"]:
        out.append("- Strukturovaná data: JSON-LD z dokumentu Správy webu vlož beze změny do "
                   "`<script type=\"application/ld+json\">` v `<head>`.")
    return out


def _header(header, variants):
    cta = header["cta"]
    nav = ("hlavní stránky z mapy domény" if header["nav"] == "source:pages" else "ruční menu")
    out = ["#### Hlavička", "",
           f"- Varianta `ds-header--{header['variant']}`" + (", `ds-header--sticky`" if header["sticky"] else "")
           + f"; menu: {nav}" + (f" ({_links(header['items'])})" if header["items"] else "") + "."]
    if header["logoAsset"]:
        out.append(f"- Logo `{header['logoAsset']}`, alt „{header['logoAlt']}“.")
    if cta["label"]:
        variant = cta["variant"] or next(iter(variants), "primary")
        out.append(f"- CTA „{cta['label']}“ → {_target(cta)} jako `ds-btn ds-btn--{variant}`.")
    out += ["", "```html", f'<header class="ds-header ds-header--{header["variant"]}">', '  <div class="ds-header__inner">',
            '    <a class="ds-header__logo" href="/"><img class="ds-header__logo-img" src="…" alt="…"></a>',
            '    <nav class="ds-header__nav" aria-label="Hlavní menu">',
            '      <a class="ds-header__link" href="/" aria-current="page">…</a>', "    </nav>", "  </div>", "</header>",
            "```"]
    return out


def _footer(footer):
    out = ["#### Patička", "", f"- Varianta `ds-footer--{footer['variant']}`."]
    out += [f"- Sloupec „{column['title']}“: {_links(column['links'])}" for column in footer["columns"]]
    if footer["social"]:
        out.append("- Sítě: " + ", ".join(f"{item['name']} `{item['url']}`" for item in footer["social"]) + ".")
    if footer["legal"]:
        out.append(f"- Právní řádek (`ds-footer__legal`): „{footer['legal']}“.")
    if footer["cookieLink"]:
        out.append("- Odkaz „Nastavení cookies“ v patičce znovu otevře cookie lištu.")
    return out + ["", "```html", f'<footer class="ds-footer ds-footer--{footer["variant"]}">',
                  '  <div class="ds-footer__inner">', '    <div class="ds-footer__columns">',
                  '      <nav aria-label="…"><h2 class="ds-footer__title">…</h2>',
                  '        <ul class="ds-footer__links"><li><a class="ds-footer__link" href="…">…</a></li></ul></nav>',
                  "    </div>", '    <ul class="ds-footer__social">…</ul>', '    <p class="ds-footer__legal">…</p>',
                  "  </div>", "</footer>", "```"]


def _cookies(gdpr):
    bar, contact = gdpr["cookieBar"], gdpr["contact"]
    if not bar["enabled"]:
        return ["#### Cookie lišta", "", "- Vypnutá. Web nesmí ukládat jiné než nezbytné cookies."]
    labels = [bar["categoryInfo"].get(key, {}).get("label") or key for key in bar["categories"]]
    policy = bar["policyPageId"] and f"stránka `{bar['policyPageId']}`" or bar["policyUrl"] and f"`{bar['policyUrl']}`"
    out = ["#### Cookie lišta", "",
           f"- `ds-cookie-bar ds-cookie-bar--{bar['position']}`, kategorie: {', '.join(labels)}"
           + (f"; zásady: {policy}" if policy else "") + ".",
           (f"- Tlačítka „{bar['acceptLabel']}“ a „{bar['rejectLabel']}“ na první vrstvě se stejnou třídou "
            f"`ds-cookie-bar__choice`, „{bar['settingsLabel']}“ otevře výběr kategorií a „{bar['saveLabel']}“ ho uloží."),
           "- Kromě `necessary` je každá kategorie předem vypnutá; zavření lišty ani posun stránky nejsou souhlas.",
           "- Skripty analytiky a marketingu se načtou až po souhlasu s jejich kategorií.",
           f"- Souhlas (kategorie, čas, verze `{bar['version']}`) platí {bar['consentDays']} dní; vyšší verze se ptá "
           "znovu." + (" Plovoucí tlačítko `ds-cookie-reopen` dovolí souhlas kdykoli změnit." if bar["reopen"] else "")]
    if contact["controller"] or contact["email"]:
        out.append(f"- Správce: {contact['controller'] or '—'}"
                   + (f", `{contact['email']}`" if contact["email"] else "")
                   + (f", pověřenec `{contact['dpoEmail']}`" if contact["dpoEmail"] else "") + ".")
    return out + ["", "```html",
                  (f'<section class="ds-cookie-bar ds-cookie-bar--{bar["position"]}" role="dialog" '
                   'aria-modal="false" aria-labelledby="cookie-title">'), '  <h2 class="ds-cookie-bar__title" id="cookie-title">…</h2>',
                  '  <p class="ds-cookie-bar__text">… <a class="ds-cookie-bar__policy" href="…">Zásady cookies</a></p>',
                  '  <fieldset class="ds-cookie-bar__categories" hidden>',
                  '    <label class="ds-cookie-bar__category"><input type="checkbox" checked disabled> Nezbytné</label>',
                  "  </fieldset>", '  <div class="ds-cookie-bar__actions">',
                  '    <button class="ds-cookie-bar__choice" type="button">Přijmout vše</button>',
                  '    <button class="ds-cookie-bar__choice" type="button">Odmítnout vše</button>',
                  ('    <button class="ds-cookie-bar__choice ds-cookie-bar__choice--settings" type="button">'
                   "Nastavení</button>"), "  </div>", "</section>", "```"]


def _email(email, affiliate):
    out = []
    if email["host"]:
        out += ["#### E-mail", "", f"- {email['provider']} `{email['host']}:{email['port']}` ({email['security']}), "
                f"odesílatel `{email['from']}`" + (f", odpovědi na `{email['replyTo']}`" if email["replyTo"] else "")
                + ".", f"- Heslo jen z `{email['secretRef'] or 'tajemství mimo repozitář'}`, nikdy do kódu ani do repa."]
    if affiliate["enabled"]:
        out += ["", "#### Affiliate", "", (f"- Parametr `?{affiliate['param']}=`, cookie "
                f"{affiliate['cookieDays']} dní (kategorie marketing), atribuce {affiliate['attribution']}.")]
        out += [f"- {program['name']}: {program['url'] or '—'}" + (f", provize {program['commission']}"
                if program["commission"] else "") for program in affiliate["programs"]]
        if affiliate["disclosure"]:
            out.append(f"- Upozornění u provizních odkazů: „{affiliate['disclosure']}“.")
    return out


def lines(settings, variants):
    """Řádky sekce `### Nastavení webu` pro README."""
    out = ["", "### Nastavení webu", "",
           ("Platí pro každou stránku webu; stránka řeší jen svoje detaily. Styly `ds-header`, `ds-footer` a "
            "`ds-cookie-bar` jsou v `components.css`."), ""]
    for part in (_seo(settings["seo"]), _header(settings["header"], variants), _footer(settings["footer"]),
                 _cookies(settings["gdpr"]), _email(settings["email"], settings["affiliate"])):
        if part:
            out += [*part, ""]
    return out[:-1]
