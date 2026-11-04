"""Zkrácený vzorek design systému pro testy (podle dema „Ember“ a vzorku Seazar formátu Design System)."""


def ember():
    return {
        "v": 1,
        "title": "Ember",
        "settings": {
            "seo": {"titleTemplate": "%s · Ember", "sitemap": True},
            "email": {"provider": "smtp", "host": "smtp.example.cz", "port": 587, "secure": True,
                      "from": "kavarna@example.cz", "secretRef": "env:SMTP_PASSWORD"},
            "buttons": {"variants": {"primary": {"label": "Objednat", "preset": "solid", "states": {
                "default": {"background": "{ember}", "color": "#120e0c", "radius": "md"},
                "hover": {"shadow": "{shadow-sm}"}}}}},
            "customCss": {"button": {"primary": ":scope:hover { animation: glow 1s ease-out; }\n"
                                                "@keyframes glow { to { opacity: 0.9; } }"}},
            "gdpr": {"cookieBar": {"enabled": True, "position": "bottom",
                                   "categories": ["necessary", "analytics"], "consentDays": 180}},
        },
        "design": {
            "readme": "# Ember\n\nKrátké věty, bez vykřičníků.",
            "tokens": {
                "color": {
                    "themes": [{"id": "light", "name": "Light"}, {"id": "dark", "name": "Dark"}],
                    "tokens": [
                        {"name": "surface", "value": {"light": "#FFF8F0", "dark": "#1c1714"}, "usage": "Podklad stránky."},
                        {"name": "ink", "value": {"light": "#2a1f1a", "dark": "#f4ebe3"}, "usage": "Text na `surface`."},
                        {"name": "ember", "value": "rgb(214 88 42)", "usage": "Primární akce."},
                        {"name": "link", "value": "{ember}"},
                    ],
                },
                "type": {
                    "fonts": [{"family": "Inter", "file": "inter.woff2", "weight": "300 800", "style": "normal"}],
                    "families": {"sans": "Inter, system-ui, sans-serif", "mono": "ui-monospace, monospace"},
                    "groups": [
                        {"name": "Text", "family": "sans", "note": "One family, four steps", "styles": [
                            {"name": "display", "fontSize": 32, "lineHeight": 40, "fontWeight": 600,
                             "letterSpacing": "-0.01em", "sample": "Dobré ráno"},
                            {"name": "body", "fontSize": "15px", "lineHeight": 1.45, "fontWeight": "normal"},
                        ]},
                        {"name": "Code", "family": "mono", "styles": [{"name": "code", "fontSize": 13}]},
                    ],
                },
                "spacing": {"note": "4px base", "tokens": [{"name": "space-1", "value": 4}, {"name": "space-1.5", "value": "6px"}]},
                "radius": {"tokens": [{"name": "radius-md", "value": "8px"}]},
                "shadow": {"tokens": [{"name": "shadow-sm", "value": {
                    "light": "0 1px 2px rgba(0, 0, 0, 0.08)", "dark": "none"}}]},
                "size": {"tokens": [{"name": "control", "value": "40px"}]},
            },
            "components": [{"name": "Card", "group": "Layout", "readme": "# Card\n\nJeden nápoj na kartě. Další text.",
                            "preview": '<article class="body" style="padding: 16px">Espresso</article>', "height": 72}],
            "assetGroups": [{"name": "Logos", "readme": "Logo v barvě `ink`.",
                             "files": [{"name": "mark.svg", "blob": "assets/Logos/mark.svg", "size": 120,
                                        "type": "image/svg+xml"}]}],
        },
    }
