#!/usr/bin/env python3
"""Rebuild Hack Tracker static files from data.json.

Run from the repo root after any data.json edit:

    python3 tools/build.py

Regenerates: index.html, sitemap.xml, feed.xml, llms.txt, llms-full.txt, og-image.png
Does not touch CNAME.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data.json"
TEMPLATE_PATH = ROOT / "tools" / "template.html"
SITE = "https://hacktracking.com"
SEV = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

# Officially assigned ISO 3166-1 alpha-2 codes. "EU" is also allowed
# for European Union institutions (an exceptionally reserved code).
ISO_3166_1_ALPHA2 = frozenset(
    """AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ
    BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ
    CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ
    DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR
    GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY
    HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP
    KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY
    MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ
    NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY
    QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ
    TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ
    VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW""".split()
)
ALLOWED_COUNTRY_CODES = ISO_3166_1_ALPHA2 | {"EU"}
COUNTRY_LABELS = {
    "AU": "Australia", "BE": "Belgium", "BR": "Brazil", "BW": "Botswana",
    "CA": "Canada", "CH": "Switzerland", "CZ": "Czechia", "DE": "Germany",
    "ES": "Spain", "ET": "Ethiopia", "EU": "European Union", "FR": "France",
    "GB": "United Kingdom", "IE": "Ireland", "IN": "India", "JP": "Japan",
    "KR": "South Korea", "LT": "Lithuania", "LU": "Luxembourg", "NO": "Norway",
    "NZ": "New Zealand", "PL": "Poland", "PT": "Portugal", "SE": "Sweden",
    "SG": "Singapore", "TH": "Thailand", "TW": "Taiwan", "UA": "Ukraine",
    "US": "United States",
}


def normalize_countries(entry):
    """Return a validated list of country codes; treat a missing field as empty."""
    countries = entry.get("countries", [])
    if countries is None:
        countries = []
    if not isinstance(countries, list):
        sys.exit(f"countries must be a list for {entry.get('org')}: {countries!r}")
    seen = set()
    clean = []
    for code in countries:
        if not isinstance(code, str):
            sys.exit(f"Bad country code for {entry.get('org')}: {code!r}")
        code = code.strip()
        if code == "UK":
            sys.exit(f"Use GB, not UK, for {entry.get('org')}")
        if not re.fullmatch(r"[A-Z]{2}", code):
            sys.exit(f"Country codes must be ISO 3166-1 alpha-2 (or EU) for {entry.get('org')}: {code!r}")
        if code not in ALLOWED_COUNTRY_CODES:
            sys.exit(f"Unknown country code {code} for {entry.get('org')}")
        if code in seen:
            sys.exit(f"Duplicate country code {code} for {entry.get('org')}")
        seen.add(code)
        clean.append(code)
    entry["countries"] = clean
    return clean


def flag_emoji(code):
    if code == "EU":
        return "🇪🇺"
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code)


def country_chips(codes):
    if not codes:
        return ""
    chips = []
    for code in codes:
        label = COUNTRY_LABELS.get(code, code)
        chips.append(
            f'<span class="country-chip" title="{esc(label)}">'
            f'<span class="flag" aria-hidden="true">{flag_emoji(code)}</span>'
            f'{esc(code)}</span>'
        )
    return f'<span class="countries">{"".join(chips)}</span>'


FONT_MONO_BOLD = "/usr/share/fonts/truetype/sand-box/google/IBM Plex Mono/IBMPlexMono-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/sand-box/google/IBM Plex Mono/IBMPlexMono-Regular.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_data():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    if "lastUpdated" not in data or "confirmed" not in data or "speculated" not in data:
        sys.exit("data.json must have lastUpdated, confirmed, and speculated")
    return data


def recency_date(entry):
    """Latest of the incident date and any later news-update date."""
    dates = [entry["date"]]
    if entry.get("updated"):
        dates.append(entry["updated"])
    return max(dates)


def sort_entries(entries):
    # Newest incident or news update first; higher severity breaks ties.
    return sorted(
        entries,
        key=lambda e: (recency_date(e), -SEV.get(e.get("severity"), 99)),
        reverse=True,
    )


def mark_top_entries(entries, n=3):
    """Rainbow-border the n highest-severity entries; recency (list order) breaks ties."""
    order = sorted(
        range(len(entries)),
        key=lambda i: (SEV.get(entries[i].get("severity"), 99), i),
    )
    for i in order[:n]:
        entries[i]["_top"] = True


def make_id(entry, used):
    org = entry["org"].lower()
    org = re.sub(r"\([^)]*\)", "", org)
    org = re.sub(r"[^a-z0-9]+", "-", org).strip("-")
    if not org:
        org = "entry"
    base = f"{org}-{entry['date'][:7]}"
    if base not in used:
        used.add(base)
        return base
    alt = f"{org}-{entry['date']}"
    if alt not in used:
        used.add(alt)
        return alt
    n = 2
    while f"{alt}-{n}" in used:
        n += 1
    slug = f"{alt}-{n}"
    used.add(slug)
    return slug


def assign_ids(data):
    used = set()
    for key in ("confirmed", "speculated"):
        for entry in data[key]:
            if not entry.get("org") or not entry.get("date"):
                sys.exit(f"Entry missing org or date: {entry!r}")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", entry["date"]):
                sys.exit(f"Bad date for {entry['org']}: {entry['date']}")
            if entry.get("updated") and not re.match(r"^\d{4}-\d{2}-\d{2}$", entry["updated"]):
                sys.exit(f"Bad updated date for {entry['org']}: {entry['updated']}")
            normalize_countries(entry)
            entry["_id"] = make_id(entry, used)
            entry["_kind"] = key


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def display_date(entry):
    if entry.get("dateLabel"):
        return entry["dateLabel"]
    d = datetime.strptime(entry["date"], "%Y-%m-%d")
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def display_updated(iso_date):
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return d.strftime("%b ") + str(d.day)


def datetime_attr(entry):
    label = (entry.get("dateLabel") or "").strip()
    if re.fullmatch(r"\d{4}", label):
        return label
    if re.fullmatch(
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{4}",
        label,
        flags=re.I,
    ):
        return entry["date"][:7]
    return entry["date"]


def search_blob(entry):
    parts = [
        entry.get("org"),
        entry.get("summary"),
        entry.get("impact"),
        entry.get("status"),
        entry.get("speculation"),
        entry.get("official"),
        " ".join(entry.get("sectors") or []),
        " ".join(entry.get("countries") or []),
        " ".join(COUNTRY_LABELS.get(c, c) for c in (entry.get("countries") or [])),
    ]
    return " ".join(p for p in parts if p)


SECTOR_ICONS = {
    "Tech": "chip", "Telecom": "signal", "Media": "signal", "Gaming": "chip",
    "Government": "gov", "Research": "gov", "Education": "gov",
    "Finance": "coin", "Crypto": "coin", "Business": "coin",
    "Consumer": "user", "Retail": "cart", "Food": "cart",
    "Healthcare": "health",
    "Aviation": "plane", "Travel": "plane",
    "Transportation": "truck", "Logistics": "truck",
    "Manufacturing": "bolt", "Energy": "bolt", "Utilities": "bolt",
    "Sports": "user",
}
SEV_LEVEL = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
_STAT_RE = re.compile(
    r"(?:[$€£]\s?\d[\d,.]*\s?(?:billion|million|thousand|[bmk]\b)?"
    r"|\b\d[\d,.]*\s?(?:billion|million|thousand)\b"
    r"|\b\d{1,3}(?:,\d{3})+\b)",
    re.I,
)
_STAT_SKIP = re.compile(r"claim|unverified|alleg|not disclosed|not confirmed|possibl|may have|reportedly|estimat", re.I)
_STAT_STOP = {"and", "or", "of", "the", "a", "an", "in", "on", "to", "for", "from", "with", "by", "at", "was", "were", "is", "are", "per", "about", "more", "than", "across", "including", "between", "who", "whose", "that"}


def key_stat(entry):
    """Pull a headline number straight from the impact text, or return None.
    Only uses a number that is already in the text; skips claims and estimates."""
    text = (entry.get("impact") or "").strip()
    sentence = re.split(r"(?<=[.;])\s+", text, maxsplit=1)[0] if text else ""
    m = _STAT_RE.search(sentence)
    # Only a lead number near the start of the first sentence, never a claim or estimate.
    if not m or m.start() > 25 or _STAT_SKIP.search(sentence) or re.search(r"\bserves?\b", sentence, re.I):
        return None
    stat = m.group(0).strip().rstrip(".,")
    tail = re.split(r"[,;:().]", sentence[m.end():], maxsplit=1)[0]
    words = []
    cut_by_and = False
    for w in re.findall(r"[A-Za-z][A-Za-z'-]*", tail):
        if w.lower() in _STAT_STOP:
            if words:
                cut_by_and = w.lower() in ("and", "or")
                break
            continue
        if words and w.lower().endswith("ly"):
            break
        words.append(w.rstrip("'"))
        if len(words) == 3 or w.endswith("'"):
            break
    if cut_by_and and words and words[0][:1].isupper():
        words = []  # e.g. "4,597 Fugaku and RIKYU users": a partial name would mislead
    lead = re.search(r"(up to(?: about)?|more than|over|nearly|almost|at least|about|roughly|around)\s*$", sentence[:m.start()], re.I)
    prefix = lead.group(1) if lead else ""
    return stat, " ".join(words), prefix


def icon(name, cls="i"):
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


def render_card(entry, rank, speculated):
    eid = entry["_id"]
    sectors = entry.get("sectors") or []
    sev = entry["severity"]
    level = SEV_LEVEL.get(sev, 1)
    meter = "".join(
        f'<i class="seg{" on" if i < level else ""}"></i>' for i in range(4)
    )
    badges = [f'<span class="badge sev-{esc(sev)}">{icon("alert")}{esc(sev)}</span>']
    if speculated:
        badges.append(f'<span class="badge unconf">{icon("eye")}Unconfirmed / speculation</span>')
    badges.extend(
        f'<span class="badge sector">{icon(SECTOR_ICONS.get(s, "hex"))}{esc(s)}</span>'
        for s in sectors
    )
    countries = entry.get("countries") or []
    chips = country_chips(countries)
    if chips:
        badges.append(chips)
    source_items = []
    for src in entry.get("sources") or []:
        source_items.append(
            f'<li><a href="{esc(src["url"])}" target="_blank" rel="noopener noreferrer">'
            f'{icon("link")}{esc(src["name"])} <span aria-hidden="true">↗</span></a></li>'
        )
    sources = (
        f'<div class="srcwrap"><span class="lbl">Sources</span><ul class="sources">{"".join(source_items)}</ul></div>'
        if source_items else ""
    )

    stat_html = ""
    st = key_stat(entry)
    if st:
        stat_html = (
            '<div class="stat" aria-hidden="true">'
            + (f'<em>{esc(st[2])}</em>' if st[2] else "")
            + f'<b>{esc(st[0])}</b>'
            + (f'<span>{esc(st[1])}</span>' if st[1] else "")
            + "</div>"
        )

    spec = ""
    if speculated:
        spec = (
            '<div class="tiles versus">'
            f'<div class="tile t-spec"><span class="lbl">{icon("eye")}What people speculated</span><p>{esc(entry.get("speculation") or "")}</p></div>'
            f'<div class="tile t-off official"><span class="lbl">{icon("shield")}Official explanation</span><p>{esc(entry.get("official") or "")}</p></div>'
            "</div>"
        )
    tiles = '<div class="tiles">'
    if entry.get("impact"):
        tiles += f'<div class="tile t-impact"><span class="lbl">{icon("bolt")}Impact</span><p>{esc(entry["impact"])}</p></div>'
    tiles += f'<div class="tile t-status"><span class="lbl">{icon("check")}Status</span><p class="status">{esc(entry.get("status") or "")}</p></div>'
    tiles += "</div>"

    top = " top" if entry.get("_top") else ""
    dates_html = (
        f'<time class="date" datetime="{esc(datetime_attr(entry))}">'
        f'{icon("clock")}{esc(display_date(entry))}</time>'
    )
    upd = entry.get("updated")
    if upd and upd > entry["date"]:
        dates_html += (
            f'<time class="fresh" datetime="{esc(upd)}">'
            f'{icon("refresh")}Updated {esc(display_updated(upd))}</time>'
        )
    us_attr = "1" if "US" in countries else "0"
    return f'''      <article class="card {esc(sev)}{top}" id="{esc(eid)}" data-severity="{esc(sev)}" data-sectors="{esc(",".join(sectors))}" data-countries="{esc(",".join(countries))}" data-us="{us_attr}" data-search="{esc(search_blob(entry))}">
        <svg class="card-cube" aria-hidden="true" focusable="false"><use href="#cube"/></svg>
        <div class="card-head">
          <span class="rank" aria-label="Rank {rank}"><small>#</small>{rank}</span>
          <div class="head-main">
            <h3>{esc(entry["org"])}</h3>
            <div class="meta">{"".join(badges)}</div>
          </div>
          <div class="head-side">
            <div class="dates">{dates_html}</div>
            <div class="meter" title="Threat level: {esc(sev)}"><span class="meter-lbl">Threat</span><span class="segs" aria-hidden="true">{meter}</span></div>
          </div>
        </div>
        <div class="card-body">
          {stat_html}
          <p class="summary">{esc(entry.get("summary") or "")}</p>
        </div>
        {spec}
        {tiles}
        {sources}
        <div class="comments-slot">
          <!-- Disqus thread placeholder. identifier={eid} url={SITE}/#{eid} shortname=hacktracking -->
          <button type="button" class="comments-toggle" data-entry-id="{esc(eid)}" aria-expanded="false" aria-controls="comments-{esc(eid)}">{icon("chat")}Comments <span class="disqus-comment-count" data-disqus-identifier="{esc(eid)}"></span></button>
          <div class="comments-panel" id="comments-{esc(eid)}" hidden>
            <div class="comments-host"></div>
          </div>
        </div>
      </article>'''


def article_body(entry, speculated):
    parts = [entry.get("summary") or ""]
    if speculated:
        if entry.get("speculation"):
            parts.append("What people speculated: " + entry["speculation"])
        if entry.get("official"):
            parts.append("Official explanation: " + entry["official"])
    if entry.get("impact"):
        parts.append("Impact: " + entry["impact"])
    if entry.get("status"):
        parts.append("Status: " + entry["status"])
    return " ".join(parts)


def json_ld(data):
    last = data["lastUpdated"]
    website_id = f"{SITE}/#website"
    confirmed_id = f"{SITE}/#confirmed-section"
    speculated_id = f"{SITE}/#speculated-section"

    graph = [
        {
            "@type": "WebSite",
            "@id": website_id,
            "name": "Hack Tracker",
            "url": f"{SITE}/",
            "description": (
                "A plain-English tracker of confirmed hacking incidents and big "
                "outages people suspected were hacks. Official explanations and "
                "sources on every entry."
            ),
            "inLanguage": "en",
            "dateModified": last,
        }
    ]

    def list_and_articles(entries, list_id, name, speculated):
        elements = []
        articles = []
        for i, entry in enumerate(entries, 1):
            url = f"{SITE}/#{entry['_id']}"
            elements.append(
                {
                    "@type": "ListItem",
                    "position": i,
                    "url": url,
                    "name": entry["org"],
                    "item": {"@id": url},
                }
            )
            art = {
                "@type": "Article",
                "@id": url,
                "headline": entry["org"],
                "name": entry["org"],
                "url": url,
                "datePublished": entry["date"],
                "dateModified": entry.get("updated") or entry["date"],
                "description": entry.get("summary") or "",
                "articleBody": article_body(entry, speculated),
                "isPartOf": {"@id": website_id},
                "inLanguage": "en",
                "keywords": ", ".join(
                    sectors_plus(entry, speculated)
                ),
            }
            if entry.get("sources"):
                art["citation"] = [
                    {"@type": "CreativeWork", "name": s["name"], "url": s["url"]}
                    for s in entry["sources"]
                ]
            articles.append(art)
        item_list = {
            "@type": "ItemList",
            "@id": list_id,
            "name": name,
            "itemListOrder": "https://schema.org/ItemListOrderAscending",
            "numberOfItems": len(entries),
            "itemListElement": elements,
        }
        return item_list, articles

    def sectors_plus(entry, speculated):
        words = list(entry.get("sectors") or [])
        words.extend(entry.get("countries") or [])
        words.extend(COUNTRY_LABELS.get(c, c) for c in (entry.get("countries") or []))
        words.append(entry.get("severity") or "")
        words.append("speculated outage" if speculated else "confirmed hack")
        return [w for w in words if w]

    clist, carticles = list_and_articles(
        data["confirmed"], confirmed_id, "Confirmed Hacks", False
    )
    slist, sarticles = list_and_articles(
        data["speculated"], speculated_id, "Speculated / Potential Hacks", True
    )
    graph.extend([clist, slist])
    graph.extend(carticles)
    graph.extend(sarticles)
    graph.append(faq_page(data))
    return {"@context": "https://schema.org", "@graph": graph}


def faq_question_name(entry):
    org = entry["org"]
    if org.lower().startswith("the "):
        return f"Was {org} a hack?"
    return f"Was the {org} a hack?"


def source_sentence(entry):
    names = [s["name"] for s in (entry.get("sources") or []) if s.get("name")]
    if not names:
        return ""
    if len(names) == 1:
        return f" Source: {names[0]}."
    return " Sources: " + ", ".join(names[:-1]) + ", and " + names[-1] + "."


def faq_page(data):
    questions = [
        {
            "@type": "Question",
            "name": "What counts as hacking?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "Internet hacking is the unauthorized access, manipulation, or "
                    "exploitation of digital devices, computer systems, and network "
                    "connections. It happens when someone finds and uses a weakness "
                    "in software, hardware, or human behavior to steal data, disrupt "
                    "services, or take control of a system."
                ),
            },
        },
        {
            "@type": "Question",
            "name": "What is the difference between confirmed hacks and speculated hacks?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "Confirmed Hacks were confirmed by the affected organization, a "
                    "government agency, or law enforcement. Numbers come from those "
                    "statements, filings, or the linked reporting. Attacker claims are "
                    "labeled as claims. Speculated / Potential Hacks are outages or "
                    "incidents where the public wondered about a hack. They are not "
                    "confirmed hacks. Each one shows what the organization or "
                    "investigators officially said."
                ),
            },
        },
        {
            "@type": "Question",
            "name": "How often is Hack Tracker updated?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "The list is reviewed and updated about every two hours during "
                    "the day, Eastern Time. It covers roughly the past 12 months, plus "
                    "a few older events that are still widely referenced. Always check "
                    "the linked sources for the latest."
                ),
            },
        },
    ]

    for entry in data["speculated"]:
        official = (entry.get("official") or "").strip()
        status = (entry.get("status") or "").strip()
        text = " ".join(p for p in (official, status) if p)
        text += source_sentence(entry)
        questions.append(
            {
                "@type": "Question",
                "name": faq_question_name(entry),
                "acceptedAnswer": {"@type": "Answer", "text": text},
            }
        )

    # A few top-severity confirmed incidents, facts only from the entry fields.
    for entry in [e for e in data["confirmed"] if e.get("_top")]:
        org = entry["org"]
        name = org
        questions.append(
            {
                "@type": "Question",
                "name": f"What happened in the {name} incident?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": (
                        f"{entry.get('summary') or ''} "
                        f"{('Impact: ' + entry['impact']) if entry.get('impact') else ''} "
                        f"{('Status: ' + entry['status']) if entry.get('status') else ''}"
                    ).strip()
                    + source_sentence(entry),
                },
            }
        )

    return {
        "@type": "FAQPage",
        "@id": f"{SITE}/#faq",
        "name": "Hack Tracker frequently asked questions",
        "mainEntity": questions,
    }


def last_updated_display(iso_date):
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return d.strftime("%B ") + str(d.day) + d.strftime(", %Y")


def build_index(data):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    confirmed_cards = "\n".join(
        render_card(e, i, False) for i, e in enumerate(data["confirmed"], 1)
    )
    speculated_cards = "\n".join(
        render_card(e, i, True) for i, e in enumerate(data["speculated"], 1)
    )
    ld = json.dumps(json_ld(data), ensure_ascii=False, indent=2)
    ld = ld.replace("</", "<\\/")
    replacements = {
        "{{JSON_LD}}": ld,
        "{{LAST_UPDATED}}": data["lastUpdated"],
        "{{LAST_UPDATED_DISPLAY}}": last_updated_display(data["lastUpdated"]),
        "{{CONFIRMED_COUNT}}": str(len(data["confirmed"])),
        "{{SPECULATED_COUNT}}": str(len(data["speculated"])),
        "{{CONFIRMED_COUNT_US}}": str(sum(1 for e in data["confirmed"] if "US" in (e.get("countries") or []))),
        "{{SPECULATED_COUNT_US}}": str(sum(1 for e in data["speculated"] if "US" in (e.get("countries") or []))),
        "{{CONFIRMED_CARDS}}": confirmed_cards,
        "{{SPECULATED_CARDS}}": speculated_cards,
    }
    html_out = template
    for key, val in replacements.items():
        html_out = html_out.replace(key, val)
    leftover = re.findall(r"\{\{[A-Z0-9_]+\}\}", html_out)
    if leftover:
        sys.exit(f"Unreplaced template placeholders: {leftover}")
    (ROOT / "index.html").write_text(html_out, encoding="utf-8")


def build_sitemap(data):
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{SITE}/</loc>\n"
        f"    <lastmod>{xml_escape(data['lastUpdated'])}</lastmod>\n"
        "    <changefreq>hourly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "  <url>\n"
        f"    <loc>{SITE}/feed.xml</loc>\n"
        f"    <lastmod>{xml_escape(data['lastUpdated'])}</lastmod>\n"
        "    <changefreq>hourly</changefreq>\n"
        "  </url>\n"
        "</urlset>\n"
    )
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")


def rfc822(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
    return d.strftime("%a, %d %b %Y %H:%M:%S GMT")


def entry_rss_description(entry, speculated):
    bits = [entry.get("summary") or ""]
    if speculated:
        if entry.get("speculation"):
            bits.append("What people speculated: " + entry["speculation"])
        if entry.get("official"):
            bits.append("Official explanation: " + entry["official"])
    if entry.get("impact"):
        bits.append("Impact: " + entry["impact"])
    if entry.get("status"):
        bits.append("Status: " + entry["status"])
    if entry.get("sources"):
        bits.append(
            "Sources: "
            + "; ".join(f"{s['name']} ({s['url']})" for s in entry["sources"])
        )
    return xml_escape(" ".join(bits))


def build_feed(data):
    items = []
    for entry in data["confirmed"]:
        items.append((entry, False))
    for entry in data["speculated"]:
        items.append((entry, True))
    items.sort(
        key=lambda pair: (recency_date(pair[0]), -SEV.get(pair[0].get("severity"), 99)),
        reverse=True,
    )

    last = data["lastUpdated"]
    built = datetime.strptime(last, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
    )
    out.append("<channel>")
    out.append("<title>Hack Tracker</title>")
    out.append(f"<link>{SITE}/</link>")
    out.append(
        "<description>Confirmed hacking incidents and outages people suspected were hacks, with official explanations and sources.</description>"
    )
    out.append("<language>en</language>")
    out.append(f"<lastBuildDate>{built.strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>")
    out.append(f'<atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>')
    for entry, speculated in items:
        kind = "Speculated / Potential Hack" if speculated else "Confirmed Hack"
        title = f"{entry['org']} — {kind}"
        link = f"{SITE}/#{entry['_id']}"
        cats = [kind, entry.get("severity") or ""] + list(entry.get("sectors") or []) + list(entry.get("countries") or [])
        out.append("<item>")
        out.append(f"<title>{xml_escape(title)}</title>")
        out.append(f"<link>{xml_escape(link)}</link>")
        out.append(f"<guid isPermaLink=\"true\">{xml_escape(link)}</guid>")
        out.append(f"<pubDate>{rfc822(recency_date(entry))}</pubDate>")
        out.append(f"<description>{entry_rss_description(entry, speculated)}</description>")
        for c in cats:
            if c:
                out.append(f"<category>{xml_escape(c)}</category>")
        out.append("</item>")
    out.append("</channel></rss>\n")
    (ROOT / "feed.xml").write_text("\n".join(out), encoding="utf-8")


def one_line_summary(entry):
    return re.sub(r"\s+", " ", (entry.get("summary") or "")).strip()


def build_llms(data):
    lines = [
        "# Hack Tracker",
        "",
        f"> A plain-English tracker of confirmed hacking incidents and outages people suspected were hacks. Official explanations and sources on every entry. Last updated {data['lastUpdated']}.",
        "",
        f"Site: {SITE}/",
        "",
        "## Confirmed Hacks",
        "",
        "Incidents confirmed by the affected organization, a government agency, or law enforcement. Most recent incident or news update first.",
        "",
    ]
    for entry in data["confirmed"]:
        lines.append(
            f"- [{entry['org']}]({SITE}/#{entry['_id']}) ({display_date(entry)}, {entry['severity']}): {one_line_summary(entry)}"
        )
    lines += [
        "",
        "## Speculated / Potential Hacks",
        "",
        "Outages or incidents where the public wondered about a hack. These are not confirmed hacks. Each entry includes the official explanation. Most recent incident or news update first.",
        "",
    ]
    for entry in data["speculated"]:
        status = (entry.get("status") or "").strip()
        extra = f" {status}" if status else ""
        lines.append(
            f"- [{entry['org']}]({SITE}/#{entry['_id']}) ({display_date(entry)}, {entry['severity']}): {one_line_summary(entry)}{extra}"
        )
    lines += [
        "",
        "## About",
        "",
        "Definition of hacking, how confirmed vs. speculated is decided, and the update cadence: "
        f"{SITE}/#about",
        "",
        "## Feeds and full text",
        "",
        f"- RSS: {SITE}/feed.xml",
        f"- Full entry text: {SITE}/llms-full.txt",
        f"- Sitemap: {SITE}/sitemap.xml",
        "",
    ]
    (ROOT / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def build_llms_full(data):
    lines = [
        "Hack Tracker",
        f"{SITE}/",
        f"Last updated: {last_updated_display(data['lastUpdated'])}",
        "",
        "What counts as hacking:",
        "Internet hacking is the unauthorized access, manipulation, or exploitation of digital devices, computer systems, and network connections. It happens when someone finds and uses a weakness in software, hardware, or human behavior to steal data, disrupt services, or take control of a system.",
        "",
        "Confirmed Hacks were confirmed by the affected organization, a government agency, or law enforcement. Numbers come from those statements, filings, or the linked reporting. Attacker claims are labeled as claims.",
        "",
        "Speculated / Potential Hacks are outages or incidents where the public wondered about a hack. They are not confirmed hacks. Each one shows what the organization or investigators officially said.",
        "",
        "The list is reviewed and updated about every two hours during the day, Eastern Time. Sorted by the most recent incident or news update first. An older entry that gets new information moves back up. Severity is a rough editorial rating, not an official score. Covers roughly the past 12 months, plus a few older events that are still widely referenced.",
        "",
    ]

    def dump_list(title, entries, speculated):
        lines.append(title)
        lines.append("")
        for i, entry in enumerate(entries, 1):
            lines.append(f"{i}. {entry['org']}")
            lines.append(f"   URL: {SITE}/#{entry['_id']}")
            lines.append(f"   Date: {display_date(entry)}")
            if entry.get("updated") and entry["updated"] > entry["date"]:
                lines.append(f"   Updated: {display_updated(entry['updated'])}")
            lines.append(f"   Severity: {entry['severity']}")
            if entry.get("sectors"):
                lines.append("   Sectors: " + ", ".join(entry["sectors"]))
            if entry.get("countries"):
                lines.append("   Countries: " + ", ".join(entry["countries"]))
            if entry.get("summary"):
                lines.append("   Summary: " + entry["summary"])
            if speculated:
                if entry.get("speculation"):
                    lines.append("   What people speculated: " + entry["speculation"])
                if entry.get("official"):
                    lines.append("   Official explanation: " + entry["official"])
            if entry.get("impact"):
                lines.append("   Impact: " + entry["impact"])
            if entry.get("status"):
                lines.append("   Status: " + entry["status"])
            if entry.get("sources"):
                lines.append("   Sources:")
                for s in entry["sources"]:
                    lines.append(f"     - {s['name']}: {s['url']}")
            lines.append("")

    dump_list("CONFIRMED HACKS", data["confirmed"], False)
    dump_list("SPECULATED / POTENTIAL HACKS", data["speculated"], True)
    (ROOT / "llms-full.txt").write_text("\n".join(lines), encoding="utf-8")


def build_og_image(data):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    w, h = 1200, 630
    bg = (11, 15, 20)
    panel = (15, 24, 34)
    line = (34, 48, 66)
    text = (230, 237, 243)
    muted = (147, 164, 184)
    accent = (61, 220, 151)
    crit = (255, 77, 94)

    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    for y in range(0, 220):
        t = y / 220
        c = tuple(int(bg[i] + (panel[i] - bg[i]) * (1 - t) * 0.7) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)
    draw.rectangle([0, h - 4, w, h], fill=accent)

    # Soft glow behind the status dot
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    cx, cy, r = 108, 200, 18
    gdraw.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(255, 77, 94, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=crit)

    brand = ImageFont.truetype(FONT_MONO_BOLD, 72)
    tag = ImageFont.truetype(FONT_SANS, 32)
    small = ImageFont.truetype(FONT_MONO, 24)
    pill = ImageFont.truetype(FONT_SANS_BOLD, 26)

    x = 150
    draw.text((x, 158), "HACK", font=brand, fill=text)
    hw = draw.textbbox((x, 158), "HACK", font=brand)[2]
    draw.text((hw + 18, 158), "TRACKER", font=brand, fill=accent)

    tagline = "Confirmed hacks vs. speculated outages"
    draw.text((80, 280), tagline, font=tag, fill=muted)

    # Count pills
    confirmed_n = len(data["confirmed"])
    speculated_n = len(data["speculated"])
    labels = [
        (f"{confirmed_n}  Confirmed", accent, (15, 42, 34), (61, 220, 151)),
        (f"{speculated_n}  Speculated", muted, (22, 32, 43), line),
    ]
    px = 80
    py = 360
    for label, fg, fill, border in labels:
        bbox = draw.textbbox((0, 0), label, font=pill)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad_x, pad_y = 22, 14
        box = [px, py, px + tw + pad_x * 2, py + th + pad_y * 2]
        draw.rounded_rectangle(box, radius=10, fill=fill, outline=border, width=2)
        draw.text((px + pad_x, py + pad_y - 2), label, font=pill, fill=fg)
        px = box[2] + 16

    draw.text((80, 540), "hacktracking.com", font=small, fill=accent)

    img.save(ROOT / "og-image.png", "PNG", optimize=True)


def main():
    data = load_data()
    data["confirmed"] = sort_entries(data["confirmed"])
    data["speculated"] = sort_entries(data["speculated"])
    assign_ids(data)
    mark_top_entries(data["confirmed"])
    mark_top_entries(data["speculated"])
    build_index(data)
    build_sitemap(data)
    build_feed(data)
    build_llms(data)
    build_llms_full(data)
    build_og_image(data)
    print(
        f"Built {len(data['confirmed'])} confirmed and {len(data['speculated'])} "
        f"speculated entries from data.json (lastUpdated {data['lastUpdated']})."
    )


if __name__ == "__main__":
    main()
