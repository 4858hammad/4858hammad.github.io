#!/usr/bin/env python3
"""Build the whole portfolio (every HTML page, sitemap, chat knowledge) from the data files.

    pip install pyyaml && python tools/build_site.py

Inputs : portfolio_data.yaml   (profile, experience, projects, hire terms)
         data/apps.json        (snapshot of the NeuralBytea apps)
Outputs: index.html, odoo.html, apps.html, experience.html, contact.html, privacy.html, 404.html,
         projects/<id>/index.html, legacy redirects, sitemap.xml, worker/src/knowledge.js

AI chat (optional, the same design as the NeuralBytea site):
  CHAT_ENDPOINT   URL of the Cloudflare Worker in worker/  -> the key never reaches the website (recommended).
  CHAT_KEY / GROQ_API_KEY  only read when running inside GitHub Actions (direct mode). The key is then injected
                  into the PUBLISHED pages, camouflaged but readable in DevTools. It is never written to the repo
                  because local builds ignore it.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
D = yaml.safe_load((ROOT / "portfolio_data.yaml").read_text(encoding="utf-8"))
APPS = json.loads((ROOT / "data/apps.json").read_text(encoding="utf-8"))
SITE, CONTACT, HIRE = D["site"], D["contact"], D["hire"]
PROJECTS = D["projects"]
NAME = SITE["name"]
SITE_URL = SITE["url"].rstrip("/")
NBSITE = "https://neuralbytea.github.io"
STORE = "https://apps.odoo.com/apps/browse?repo_maintainer_id=1172096"
FORM_ACTION = "https://formspree.io/f/mzdwrpyp"
CV_PDF, ATS_PDF = "assets/Hammad_Ali_Senior_Odoo_Developer_CV.pdf", "assets/Hammad-Ali-CV-ATS.pdf"
TODAY = dt.date.today().isoformat()
N_APPS = len(APPS)

# ------------------------------------------------------------------ chat configuration
CHAT_ENDPOINT = os.environ.get("CHAT_ENDPOINT", "").strip() or str(SITE.get("chat_endpoint") or "").strip()
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"
CHAT_KEY = ""
if IN_CI and not CHAT_ENDPOINT:
    CHAT_KEY = (os.environ.get("CHAT_KEY") or os.environ.get("GROQ_API_KEY") or "").strip()
CHAT_ON = bool(CHAT_ENDPOINT or CHAT_KEY)


def _scramble(key: str) -> list[str]:
    b = base64.b64encode(key[::-1].encode()).decode()
    n = -(-len(b) // 4)
    return [b[i:i + n] for i in range(0, len(b), n)]


e = lambda v: html.escape("" if v is None else str(v), quote=True)  # noqa: E731


def lastmod(path: Path) -> str:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        return out or TODAY
    except Exception:
        return TODAY


# ------------------------------------------------------------------ project helpers
def words(txt: str, *needles: str) -> bool:
    return any(re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", txt) for n in needles)


FILTERS = [("portals", "Portals"), ("payments", "Payments"), ("integrations", "Integrations"), ("hr", "HR & Payroll"),
           ("manufacturing", "Manufacturing"), ("accounting", "Accounting"), ("migration", "Migration"),
           ("ai", "AI"), ("owl", "OWL & dashboards"), ("mobile", "Mobile")]


def tags_for(p: dict) -> list[str]:
    txt = " ".join([p["title"], " ".join(p.get("tags") or []), " ".join(p.get("modules") or [])]).lower()
    t = []
    if words(txt, "portal", "portals"): t.append("portals")
    if words(txt, "payment", "payments", "mastercard"): t.append("payments")
    if words(txt, "api", "apis", "integration", "sage", "meta", "gohighlevel", "webhook"): t.append("integrations")
    if words(txt, "hr", "payroll", "attendance", "loan", "loans", "time off", "timesheets", "biometric"): t.append("hr")
    if words(txt, "mrp", "bom", "manufacturing"): t.append("manufacturing")
    if words(txt, "accounting", "invoicing"): t.append("accounting")
    if words(txt, "migration"): t.append("migration")
    if words(txt, "ai", "mcp"): t.append("ai")
    if words(txt, "owl", "analytics", "dashboard", "dashboards", "chart.js"): t.append("owl")
    if p.get("category") == "android" or words(txt, "react native", "kotlin", "android"): t.append("mobile")
    return t


def versions(p: dict) -> list[str]:
    return re.findall(r"Odoo (\d+)", p.get("odoo_version") or "")


def rel_root(path: str) -> str:
    return "../" * (len(Path(path).parts) - 1)


def project_url(p: dict) -> str:
    return f"projects/{p['id']}/"


def og_for(p: dict | None) -> str:
    if p and (ROOT / f"assets/images/og/{p['id']}.png").exists():
        return f"assets/images/og/{p['id']}.png"
    return "assets/images/og-cover.png"


# ------------------------------------------------------------------ layout
def head(title: str, desc: str, path: str, root: str, og: str, extra: str = "") -> str:
    url = SITE_URL + "/" + ("" if path == "index.html" else (path[:-10] if path.endswith("/index.html") else path))
    cfg = ""
    if CHAT_ENDPOINT:
        cfg = f'<script>window.HA_CHAT={json.dumps({"endpoint": CHAT_ENDPOINT, "site": SITE_URL})}</script>\n'
    elif CHAT_KEY:
        cfg = f'<script>window.HA_CHAT={json.dumps({"mode": "direct", "k": _scramble(CHAT_KEY), "site": SITE_URL, "model": "openai/gpt-oss-20b"})}</script>\n'
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="author" content="{NAME}"><meta name="theme-color" content="#ffffff">
<meta property="og:type" content="website"><meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{SITE_URL}/{og}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{SITE_URL}/{og}">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml"><link rel="icon" href="{root}favicon.ico" sizes="any"><link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Sora:wght@500;600;700;800&display=swap">
<link rel="stylesheet" href="{root}assets/style.css">
<script defer src="{root}assets/site.js"></script>
{cfg}<script defer src="{root}assets/chat.js"></script>
{extra}
</head>"""


NAV = [("home", "/", "Home"), ("projects", "odoo.html", "Projects"), ("apps", "apps.html", "Apps"),
       ("experience", "experience.html", "Experience"), ("contact", "contact.html", "Contact")]


def nav(root: str, active: str) -> str:
    links = "".join(f'<a href="{h if h.startswith("/") else root + h}"{" class=on" if k == active else ""}>{l}</a>' for k, h, l in NAV)
    ask = '<button type="button" class="ask-ai" data-hac-open>✦ Ask AI</button>' if CHAT_ON else ""
    return f"""<header class="nav"><div class="wrap nav-in">
<a class="brand" href="/" aria-label="{NAME} home"><img class="brand-mark" src="{root}assets/images/ha-mark.svg" width="46" height="46" alt=""><span class="brand-txt"><b>Hammad <i>Ali</i></b><small>Odoo Technical Lead</small></span></a>
<nav id="menu" aria-label="Main">{links}{ask}</nav>
<a class="btn btn-sm btn-primary nav-cta" href="{root}contact.html">Hire me</a>
<button class="burger" aria-label="Menu" aria-controls="menu"><i></i><i></i></button>
</div></header>"""


def footer(root: str) -> str:
    return f"""<footer class="foot"><div class="wrap foot-grid">
<div><a class="brand brand-lg" href="/" aria-label="{NAME} home"><img class="brand-mark" src="{root}assets/images/ha-mark.svg" width="64" height="64" alt=""><span class="brand-txt"><b>Hammad <i>Ali</i></b><small>Odoo Technical Lead</small></span></a>
<p class="muted">Production Odoo systems from workflow to deployment. Founder of NeuralBytea, {N_APPS} apps on the Odoo Apps Store.</p>
<a href="mailto:{CONTACT['email']}">{CONTACT['email']}</a><span class="muted">{CONTACT['location']}, working remotely</span></div>
<div><h4>Explore</h4>{"".join(f'<a href="{h if h.startswith("/") else root + h}">{l}</a>' for _, h, l in NAV)}</div>
<div><h4>Work with me</h4><a href="{root}contact.html">Hire me</a><a href="{root}{CV_PDF}">Download CV</a><a href="{root}{ATS_PDF}">ATS-friendly CV</a><a href="{CONTACT['linkedin']}" target="_blank" rel="noopener">LinkedIn ↗</a><a href="{CONTACT['github']}" target="_blank" rel="noopener">GitHub ↗</a></div>
<div><h4>My apps</h4><a href="{root}apps.html">All {N_APPS} apps</a><a href="{NBSITE}/" target="_blank" rel="noopener">NeuralBytea ↗</a><a href="{STORE}" target="_blank" rel="noopener">Odoo Apps Store ↗</a><h4 style="margin-top:22px">Legal</h4><a href="{root}privacy.html">Privacy Policy</a></div>
</div><div class="wrap foot-bar"><span>© {dt.date.today().year} {NAME}. All rights reserved.</span><span>Odoo is a trademark of Odoo S.A.</span></div></footer>"""


def page(title, desc, path, active, body, extra="", og="assets/images/og-cover.png") -> str:
    root = rel_root(path)
    return (head(title, desc, path, root, og, extra) + f'<body>\n<div class="aurora"></div>\n<a class="skip" href="#main">Skip to content</a>\n{nav(root, active)}\n'
            f'<main id="main">{body}</main>\n{footer(root)}\n</body></html>\n')


def write(path: str, content: str) -> None:
    f = ROOT / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")


# ------------------------------------------------------------------ components
def car(items: list[str]) -> str:
    return ('<div class="carousel reveal" data-carousel><div class="car-track">' + "".join(f'<div class="car-item">{i}</div>' for i in items)
            + '</div><button class="car-btn prev" aria-label="Previous">‹</button><button class="car-btn next" aria-label="Next">›</button><div class="car-dots"></div></div>')


TYPE_LABEL = [("portals", "Portal"), ("payments", "Payments"), ("integrations", "Integration"), ("hr", "HR & Payroll"), ("manufacturing", "Manufacturing"),
              ("accounting", "Accounting"), ("migration", "Migration"), ("ai", "AI"), ("owl", "OWL dashboard"), ("mobile", "Mobile app")]


def platform_of(p: dict) -> tuple[str, str]:
    """(label, css class) saying which technology the project is built on."""
    if p.get("category") == "android":
        return "Mobile app", "pf-mobile"
    v = versions(p)
    return ("Odoo " + "/".join(v) if v else "Odoo"), "pf-odoo"


def project_card(p: dict, root: str, reveal: bool = True, lazy: bool = True) -> str:
    q = " ".join([p["title"], p.get("short_desc", ""), p.get("client", ""), " ".join(p.get("tags") or []), " ".join(p.get("tech_stack") or [])]).lower()
    vb = "".join(f'<i class="vb">{v}</i>' for v in versions(p)) or f'<i class="vb">{e((p.get("tags") or ["App"])[0])}</i>'
    pl, pcls = platform_of(p)
    tg = tags_for(p)
    types = [lbl for k, lbl in TYPE_LABEL if k in tg][:2]
    type_html = "".join(f'<span class="chip">{e(t)}</span>' for t in types)
    stack = "".join(f'<span class="stk">{e(t)}</span>' for t in (p.get("tech_stack") or [])[:4])
    return f"""<article class="card app pc{' reveal' if reveal else ''}" data-tags="{' '.join(tg)}" data-q="{e(q)}">
<div class="shot pj"><img src="{root}{p['image']}" alt="{e(p['title'])}: solution diagram" width="1800" height="600"{' loading="lazy"' if lazy else ''}></div>
<div class="app-body"><div class="app-top"><span class="pf {pcls}">{e(pl)}</span>{type_html}</div>
<h3><a class="card-link" href="{root}{project_url(p)}">{e(p['title'])}</a></h3><p>{e(p.get('short_desc', ''))}</p>
<div class="by">{e(p.get('client', ''))} · {e(p.get('year', ''))}</div>
<div class="stack">{stack}</div>
<div class="app-foot"><span class="more">View case study <i>→</i></span><span class="vbs" title="Odoo version">{vb}</span></div></div></article>"""


def app_card(a: dict) -> str:
    price = "Free" if a["price"] in ("", "0") else f"${a['price']}"
    vb = "".join(f'<i class="vb">{v}</i>' for v in a["versions"])
    q = (a["name"] + " " + a["desc"]).lower()
    return f"""<a class="card app reveal" href="{NBSITE}/apps/{a['id']}/" target="_blank" rel="noopener" data-tags="{a['line']}" data-q="{e(q)}">
<div class="shot"><img src="{NBSITE}/images/apps/{a['image']}" alt="{e(a['name'])} for Odoo" width="1000" height="500" loading="lazy"></div>
<div class="app-body"><div class="app-top"><span class="chip fam-{a['line']}">{LINE_LABEL[a['line']]}</span>{'<span class="chip-new">New</span>' if a.get('new') else ''}<span class="price">{price}</span></div>
<h3>{e(a['name'])}</h3><p>{e(a['desc'])}</p>
<div class="app-foot"><span class="more">View on NeuralBytea <i>↗</i></span><span class="vbs" title="Odoo versions">{vb}</span></div></div></a>"""


LINES = [("portals", "Portals"), ("payments", "Payments"), ("int", "Integrations"), ("hr", "HR & Payroll"), ("dash", "Dashboards"),
         ("ai", "AI Assistant"), ("edu", "Education"), ("ui", "Backend UI")]
LINE_LABEL = dict(LINES)


def chips_bar(grid_id: str, items: list[tuple[str, str, int]], search_id: str = "") -> str:
    btns = '<button type="button" class="on" data-f="all" aria-pressed="true">All</button>' + "".join(
        f'<button type="button" data-f="{k}" aria-pressed="false">{e(l)} <small>{n}</small></button>' for k, l, n in items if n)
    return f'<div class="fchips" data-for="{grid_id}" data-search="{search_id}" role="group" aria-label="Filter">{btns}</div>'


def timeline(items: list[dict], full: bool) -> str:
    out = []
    for x in items:
        hl = ""
        if full and x.get("highlights"):
            hl = "<ul>" + "".join(f"<li>{e(h)}</li>" for h in x["highlights"]) + "</ul>"
        meta = f'<span class="tl-meta">{e(x["meta"])}</span>' if x.get("meta") else ""
        out.append(f"""<div class="card tl-item reveal"><div class="tl-top"><div><div class="tl-role">{e(x['role'])}</div><div class="tl-co">{e(x['company'])}</div></div><div class="tl-when">{e(x['period'])}</div></div>
{meta}<p class="muted">{e(x.get('summary', ''))}</p>{hl}</div>""")
    return '<div class="tl">' + "".join(out) + "</div>"


def hire_cards() -> str:
    rows = [("Rate", HIRE["rate"], HIRE["rate_note"]), ("Availability", "Open to work", HIRE["availability"]),
            ("Time zone", HIRE["timezone"], HIRE["timezone_note"]), ("How we can work", "Contract or full-time", " · ".join(HIRE["engagements"]) + ". " + HIRE["response"])]
    return '<div class="grid hire-grid">' + "".join(f'<div class="card hire reveal"><small>{e(k)}</small><b>{e(v)}</b><p>{e(n)}</p></div>' for k, v, n in rows) + "</div>"


def cta(title_html: str, text: str, root: str) -> str:
    return f"""<section class="wrap"><div class="cta reveal"><h2>{title_html}</h2><p>{text}</p>
<div class="btn-row center"><a class="btn btn-primary" href="{root}contact.html">Contact me</a><a class="btn btn-ghost" href="{root}{CV_PDF}">Download CV ↓</a></div></div></section>"""


# ------------------------------------------------------------------ pages
FEATURED = sorted([p for p in PROJECTS if p.get("featured")], key=lambda p: -int(p.get("year") or 0))[:6]
STATS = [(str(N_APPS), "Apps published on the Odoo Apps Store"),
         ("250+", "Employees use the HR and attendance systems I built"),
         ("~200", "Card payments a day through a payment system I built"),
         ("54,000+", "Old records moved safely into a new system")]
SERVICES = [("🧩", "Custom modules & OWL", "Odoo 16–20, Community and Enterprise. ORM logic, QWeb, and OWL/JavaScript dashboards that ship to production."),
            ("🔌", "Integrations & payments", "Mastercard Hosted Checkout, Sage, Meta, GoHighLevel and bidirectional REST APIs with callbacks and reconciliation."),
            ("🚚", "Migrations & data", "Odoo 16→17 HRMS migration and a 54,000+ record backfill in controlled batches, with validation and regression testing."),
            ("🔐", "Portals & security", "Employee, doctor, customer and field-sales portals with ACLs, record rules and territory-aware visibility."),
            ("📊", "Accounting, MRP & HR", "Accounting, Sales, Purchase, Inventory, MRP/BOM, CRM and Payroll. Functional depth, not just code."),
            ("🚀", "DevOps & leadership", "Odoo.sh, Ubuntu, Nginx, PostgreSQL, GitHub Actions CI/CD, plus code review and mentoring for a team of four.")]
STEPS = [("Understand the workflow", "I start from how the business actually works: the people, the documents and the numbers that must add up."),
         ("Design it for Odoo", "Standard Odoo where it fits, custom modules where it pays off, with access rights and upgrades in mind."),
         ("Build and test", "Python, OWL and QWeb written to Odoo standards, tested with real data and user acceptance before go-live."),
         ("Deploy and support", "Odoo.sh or Linux deployment, backups, training and day-to-day production support.")]


def tech_route() -> str:
    def has(p, *keys):
        t = " ".join(p.get("tech_stack") or []).lower()
        return any(k in t for k in keys)
    n = len(PROJECTS)
    rows = [("Python", "Odoo ORM, Django, Flask, REST APIs", ("python", "django", "flask", "odoo orm")),
            ("SQL / PostgreSQL", "Reporting, migrations, query tuning", ("postgres", "sql")),
            ("JavaScript", "OWL dashboards, portals, React Native", ("javascript", "owl", "react", "chart.js")),
            ("XML / QWeb", "Views, portal pages, PDF reports", ("qweb", "xml")),
            ("Kotlin", "Android app", ("kotlin",))]
    stops = []
    counted = sorted([(name, note, sum(1 for p in PROJECTS if has(p, *keys))) for name, note, keys in rows], key=lambda x: -x[2])
    for name, note, c in counted:
        pct = round(100 * c / n)
        stops.append(f'<li class="tr-stop" style="--v:{pct}"><span class="tr-pin"><span class="tr-dot" aria-hidden="true"></span></span><span class="tr-name">{e(name)}</span>'
                     f'<span class="tr-val"><strong>{pct}%</strong> {c} of {n} projects</span><span class="tr-bar" aria-hidden="true"><span></span></span><span class="tr-note">{e(note)}</span></li>')
    ai = [("Claude", "Built a read-only Claude connector for Odoo (MCP); my main coding assistant"),
          ("Codex", "Code generation and refactoring"),
          ("GitHub Copilot", "Inline suggestions in VS Code"),
          ("Groq", "Powers the Ask AI assistant on this site")]
    ai_html = "".join(f'<li class="tr-stop" style="--v:60"><span class="tr-pin"><span class="tr-dot" aria-hidden="true"></span></span><span class="tr-name">{e(a)}</span><span class="tr-note">{e(t)}</span></li>' for a, t in ai)
    return f"""<section class="wrap sec tr" id="tech-route" aria-labelledby="tr-title"><div class="sec-head reveal"><span class="eyebrow">My tech route</span><h2 id="tr-title">The languages and AI tools behind my work</h2>
<p>Each stop is a language I have shipped production work in. The number shows how many of my {n} case studies used it.</p></div>
<div class="tr-route"><div class="tr-line-head"><span class="tr-badge">Line 1</span><h3>Languages</h3></div><ol class="tr-stops">{"".join(stops)}</ol></div>
<div class="tr-route tr-route--ai"><div class="tr-line-head"><span class="tr-badge">Line 2</span><h3>AI tools</h3></div><ol class="tr-stops">{ai_html}</ol></div>
<p class="tr-foot muted">Source: tech stacks listed on my case studies.</p></section>"""


def home() -> str:
    root = ""
    stack = "".join(f'<div class="float f{i + 1}"><img src="{p["image"]}" alt="{e(p["title"])}: solution diagram" width="1800" height="600"></div>' for i, p in enumerate(FEATURED[:3]))
    stats = "".join(f'<div class="stat reveal"><b>{e(v)}</b><span>{e(l)}</span></div>' for v, l in STATS)
    fams = "".join(f'<div class="card fam reveal"><div class="ico">{i}</div><h3>{e(t)}</h3><p>{e(d)}</p></div>' for i, t, d in SERVICES)
    for k, tip in (("OWL", "Odoo's front-end framework for dashboards and screens"), ("QWeb", "Odoo's templating for web pages and PDF reports"), ("MRP", "Manufacturing planning: bills of materials and production orders")):
        fams = fams.replace(k, f'<abbr title="{tip}">{k}</abbr>', 1)
    tech = "".join(f"<span>{t}</span>" for t in ["Odoo 16–20", "Python", "OWL", "JavaScript", "PostgreSQL", "QWeb", "REST APIs", "Odoo.sh", "Docker", "Nginx",
                                                 "GitHub Actions", "Accounting", "MRP / BOM", "HR & Payroll", "CRM", "Portals", "Payments"])
    counts = {k: sum(1 for a in APPS if a["line"] == k) for k, _ in LINES}
    chips = "".join(f'<a href="apps.html?line={k}">{l} · {counts[k]}</a>' for k, l in LINES if counts[k])
    shot = next((a for a in APPS if a.get("new")), APPS[0])
    steps = "".join(f'<div class="step glass reveal"><h3>{e(t)}</h3><p>{e(d)}</p></div>' for t, d in STEPS)
    qs = ["What Odoo projects has Hammad delivered?", "Which Odoo versions does he work with?", "Does he have manufacturing experience?", "How can I hire him?"]
    askai = ""
    if CHAT_ON:
        askai = ('<section class="wrap sec askai-sec"><div class="askai reveal"><div class="askai-copy"><span class="eyebrow">AI assistant</span>'
                 "<h2>Ask my AI assistant</h2><p>Get quick answers about my projects, skills, experience and availability. In English, Urdu or Roman Urdu.</p>"
                 '<div class="askai-chips">' + "".join(f'<button type="button" data-hac-ask="{e(q)}">{e(q)}</button>' for q in qs) +
                 '</div><button type="button" class="btn btn-primary" data-hac-open>✦ Start chatting</button></div>'
                 '<div class="askai-demo" aria-hidden="true"><div class="d-me">Which Odoo versions does he work with?</div>'
                 '<div class="d-bot">Hammad works with <b>Odoo 16 to 20</b>, and his published apps cover Odoo 17 to 20.</div>'
                 '<div class="d-me">Has he built payment integrations?</div><div class="d-bot">Yes: a <b>Mastercard Hosted Checkout</b> provider handling about 200 payments a day.</div></div></div></section>')
    body = f"""
<section class="hero wrap">
 <div class="hero-copy">
  <span class="pill"><i class="dot"></i>Open to a remote Odoo Technical Lead role</span>
  <h1>I build production Odoo systems from workflow to <em>deployment.</em></h1>
  <p class="lead">I build the business software companies run on every day: HR and payroll, sales, payments and manufacturing, all inside Odoo. My systems serve 250+ employees in production, and I have published {N_APPS} apps through my own studio, NeuralBytea.</p>
  <div class="btn-row"><a class="btn btn-primary" href="odoo.html">View projects</a><a class="btn btn-ghost" href="{CV_PDF}">Download CV ↓</a><a class="btn btn-ghost" href="contact.html">Let’s talk →</a></div>
  <ul class="trust"><li>Odoo 16–20 · {N_APPS} published apps</li><li>Enterprise &amp; Odoo.sh</li><li>Led a team of 4</li><li>Remote-ready</li></ul>
 </div>
 <div class="hero-art" aria-hidden="true"><div class="glow"></div>{stack}</div>
</section>
<section class="wrap stats">{stats}</section>
{askai}<section class="wrap"><div class="marquee" aria-hidden="true"><div class="track">{tech}{tech}</div></div></section>
<section class="wrap sec"><div class="sec-head reveal"><span class="eyebrow">Selected work</span><h2>Featured projects</h2><p>Real systems with real numbers: users, orders, payments and records.</p><a class="see" href="odoo.html">All {len(PROJECTS)} projects →</a></div>
 {car([project_card(p, root, reveal=False, lazy=False) for p in FEATURED])}</section>
<section class="wrap sec"><div class="sec-head reveal"><span class="eyebrow">What I do</span><h2>End-to-end Odoo engineering</h2><p>From the first requirements call to production support, one developer who can own the whole path.</p></div>
 <div class="grid fam-grid">{fams}</div></section>
{tech_route()}
<section class="wrap sec"><div class="edu reveal"><div class="edu-copy"><span class="eyebrow">My studio · NeuralBytea</span>
 <h2>{N_APPS} Odoo apps on the Odoo Apps Store</h2>
 <p>Portals, payment providers, integrations, HR and payroll tools, dashboards, an AI assistant, school management and backend UI. I design, build, publish and support every app, for Odoo 17 to 20.</p>
 <div class="edu-chips">{chips}</div>
 <div class="btn-row"><a class="btn btn-primary" href="apps.html">Browse the apps</a><a class="btn btn-ghost" href="{STORE}" target="_blank" rel="noopener">Odoo Apps Store ↗</a></div></div>
 <a class="edu-shot" href="apps.html"><img src="{NBSITE}/images/apps/{shot['image']}" alt="{e(shot['name'])} for Odoo" loading="lazy" width="1000" height="500"></a></div></section>
<section class="band"><div class="wrap"><div class="sec-head reveal light"><span class="eyebrow">How I work</span><h2>From a business need to a working system</h2></div>
 <div class="steps">{steps}</div></div></section>
<section class="wrap sec"><div class="sec-head reveal"><span class="eyebrow">Journey</span><h2>From developer to technical lead</h2><a class="see" href="experience.html">Full experience →</a></div>
 {timeline([x for x in D['experience'] if not re.search('intern', x['role'], re.I)], full=False)}</section>
<section class="wrap sec" id="hire"><div class="sec-head reveal"><span class="eyebrow">Work with me</span><h2>Hire me: rates &amp; availability</h2><p>Clear terms up front. Rates are a starting point and negotiable.</p></div>
 {hire_cards()}</section>
{cta('Have an Odoo project <span class="grad">or a role in mind?</span>', "Send a short note and I will reply within one business day.", root)}"""
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Person", "@id": f"{SITE_URL}/#person", "name": NAME, "url": SITE_URL + "/", "image": f"{SITE_URL}/assets/images/og-cover.png",
         "jobTitle": "Senior Odoo Developer", "description": SITE["description"], "email": "mailto:" + CONTACT["email"],
         "address": {"@type": "PostalAddress", "addressLocality": "Lahore", "addressRegion": "Punjab", "addressCountry": "PK"},
         "worksFor": [{"@type": "Organization", "name": "TTI Testing Laboratories"}, {"@type": "Organization", "name": "Big Binary Tech"}],
         "alumniOf": {"@type": "CollegeOrUniversity", "name": "Lahore Garrison University"},
         "knowsAbout": ["Odoo ERP", "Odoo 18", "Odoo 19", "Odoo 20", "Python", "PostgreSQL", "OWL Framework", "JavaScript", "QWeb", "REST APIs", "Odoo Accounting", "Odoo MRP", "Payment Providers", "Odoo.sh", "GitHub Actions"],
         "sameAs": [CONTACT["linkedin"], CONTACT["github"], NBSITE + "/"]},
        {"@type": "Organization", "@id": f"{NBSITE}/#org", "name": "NeuralBytea", "url": NBSITE + "/", "founder": {"@id": f"{SITE_URL}/#person"}},
        {"@type": "WebSite", "@id": f"{SITE_URL}/#website", "url": SITE_URL + "/", "name": NAME, "publisher": {"@id": f"{SITE_URL}/#person"}}]}
    return page(f"{NAME} — Senior Odoo Developer & Technical Lead | Odoo 16–20",
                f"Senior Odoo Developer, 3+ years across Odoo 16–20. Founder of NeuralBytea ({N_APPS} published Odoo apps). ERP modules, OWL, portals, payments, integrations.",
                "index.html", "home", body, f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>')


def projects_page() -> str:
    root = ""
    ordered = sorted(PROJECTS, key=lambda p: (-int(p.get("year") or 0), 0 if p.get("featured") else 1))
    counts = {k: sum(1 for p in PROJECTS if k in tags_for(p)) for k, _ in FILTERS}
    cards = "".join(project_card(p, root, reveal=False) for p in ordered)
    body = f"""
<section class="wrap page-hero"><div class="crumb"><a href="/">Home</a> / Projects</div>
 <span class="eyebrow" style="display:block;margin-top:14px">Case studies</span><h1>Odoo projects: modules, integrations &amp; migrations</h1>
 <p class="lead">{len(PROJECTS)} delivered projects: custom modules, OWL front-ends, payment gateways, Sage and REST API integrations, BOM versioning, HR automation and version migrations. Each one has scope, modules, stack and outcomes.</p></section>
<section class="wrap">
 <div class="filters"><input id="pq" type="search" placeholder="Search projects, clients or tech…" aria-label="Search projects"><span class="muted" id="pgrid-count">{len(PROJECTS)} shown</span></div>
 {chips_bar("pgrid", [(k, l, counts[k]) for k, l in FILTERS], "pq")}
 <div class="grid app-grid" id="pgrid">{cards}</div>
 <p class="muted" id="pgrid-none" hidden style="margin-top:20px">No projects match. Try another filter.</p></section>
{cta('Need something <span class="grad">like this built?</span>', "Tell me about your workflow and Odoo version, and I will tell you how I would approach it.", root)}"""
    return page(f"Odoo Projects: Custom Modules, Integrations &amp; Migrations | {NAME}".replace("&amp;", "&"),
                f"{len(PROJECTS)} delivered Odoo projects: custom modules, OWL front-ends, payment gateways, Sage and REST API integrations, BOM versioning, HR automation and migrations.",
                "odoo.html", "projects", body)


def project_page(p: dict, i: int, ordered: list[dict]) -> str:
    root = "../../"
    v = p.get("odoo_version")
    tags = "".join(f'<span class="tag">{e(t)}</span>' for t in p.get("tags") or [])
    hl = "".join(f"<li>{e(h)}</li>" for h in p.get("highlights") or [])
    mods = "".join(f"<span class='tag'>{e(m)}</span>" for m in p.get("modules") or [])
    stack = "".join(f"<span class='tag'>{e(t)}</span>" for t in p.get("tech_stack") or [])
    facts = [("Client", p.get("client", "")), ("Year", p.get("year", ""))] + ([("Odoo version", v)] if v else []) + [("Role", p.get("role", "Developer"))]
    dl = "".join(f"<dt>{k}</dt><dd>{e(val)}</dd>" for k, val in facts)
    rel = [q for q in ordered if q["id"] != p["id"] and set(tags_for(q)) & set(tags_for(p))][:3] or [q for q in ordered if q["id"] != p["id"]][:3]
    related = "".join(project_card(q, root, reveal=False) for q in rel)
    cat = "Android Projects" if p.get("category") == "android" else "Odoo ERP Projects"
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": cat, "item": SITE_URL + "/odoo.html"},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": f"{SITE_URL}/{project_url(p)}"}]},
        {"@type": "CreativeWork", "name": p["title"], "description": p.get("short_desc", ""), "url": f"{SITE_URL}/{project_url(p)}",
         "dateCreated": str(p.get("year", "")), "author": {"@type": "Person", "@id": f"{SITE_URL}/#person", "name": NAME},
         "keywords": ", ".join(p.get("tags") or [])}]}
    body = f"""
<section class="wrap page-hero slim"><div class="crumb"><a href="/">Home</a> / <a href="{root}odoo.html">Projects</a> / {e(p['title'])}</div></section>
<section class="wrap detail"><article class="detail-main">
 <div class="shot big pj"><img src="{root}{p['image']}" alt="{e(p['title'])}: solution diagram" width="1800" height="600"></div>
 <div class="chips-row" style="margin-top:20px">{tags}</div>
 <h1>{e(p['title'])}</h1><p class="lead">{e(p.get('short_desc', ''))}</p>
 <h2 class="h3">About this project</h2><p class="body">{e(p.get('full_desc') or p.get('short_desc', ''))}</p>
 {f'<h2 class="h3">Key deliverables</h2><ul class="feat">{hl}</ul>' if hl else ''}
 </article>
 <aside class="detail-side"><div class="card buy"><h4 style="margin-top:0">Project facts</h4><dl>{dl}</dl>
  {f'<h4>Modules used</h4><div class="tags">{mods}</div>' if mods else ''}{f'<h4>Tech stack</h4><div class="tags">{stack}</div>' if stack else ''}
  <a class="btn btn-primary block" href="{root}contact.html?subject={e(p['title'])}">Discuss a similar project</a>
  <a class="btn btn-ghost block" href="{root}odoo.html">← All projects</a></div></aside></section>
<section class="wrap sec"><div class="sec-head"><span class="eyebrow">Keep reading</span><h2>Related projects</h2></div><div class="grid app-grid">{related}</div></section>"""
    return page(f"{p['title']}{' — ' + v if v else ''} Case Study | {NAME}", p.get("short_desc", ""), project_url(p) + "index.html", "projects", body,
                f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>', og_for(p))


def apps_page() -> str:
    root = ""
    counts = {k: sum(1 for a in APPS if a["line"] == k) for k, _ in LINES}
    body = f"""
<section class="wrap page-hero"><div class="crumb"><a href="/">Home</a> / Apps</div>
 <span class="eyebrow" style="display:block;margin-top:14px">My studio · NeuralBytea</span><h1>{N_APPS} Odoo apps I design, build and publish</h1>
 <p class="lead">Portals, payments, integrations, HR, dashboards, an AI assistant, school management and backend UI for Odoo 17 to 20. Every app is on the Odoo Apps Store.</p>
 <div class="btn-row"><a class="btn btn-primary" href="{NBSITE}/" target="_blank" rel="noopener">Visit NeuralBytea ↗</a><a class="btn btn-ghost" href="{STORE}" target="_blank" rel="noopener">Odoo Apps Store ↗</a></div></section>
<section class="wrap">
 <div class="filters"><input id="aq" type="search" placeholder="Search apps…" aria-label="Search apps"><span class="muted" id="agrid-count">{N_APPS} shown</span></div>
 {chips_bar("agrid", [(k, l, counts[k]) for k, l in LINES], "aq")}
 <div class="grid app-grid" id="agrid">{"".join(app_card(a) for a in APPS)}</div>
 <p class="muted" id="agrid-none" hidden style="margin-top:20px">No apps match. Try another filter.</p></section>
{cta('Need an app <span class="grad">built or customised?</span>', "I build custom Odoo modules, portals and integrations at a fixed price or hourly.", root)}"""
    return page(f"Odoo Apps by {NAME} (NeuralBytea) | {N_APPS} Apps for Odoo 17–20",
                f"{N_APPS} Odoo apps for Odoo 17–20 by {NAME} (NeuralBytea): portals, payments, integrations, HR, dashboards, AI assistant, education and backend UI.",
                "apps.html", "apps", body)


def experience_page() -> str:
    root = ""
    skills = "".join(f'<div class="card info reveal"><h3>{e(g["category"])}</h3><div class="tags">{"".join(f"<span class=tag>{e(i)}</span>" for i in g["items"])}</div></div>' for g in D["skills"])
    body = f"""
<section class="wrap page-hero"><div class="crumb"><a href="/">Home</a> / Experience</div>
 <span class="eyebrow" style="display:block;margin-top:14px">{e(NAME)}</span><h1>Senior Odoo Developer &amp; Technical Lead</h1>
 <p class="lead">{e(SITE['description'])}</p>
 <div class="btn-row"><a class="btn btn-primary" href="{CV_PDF}">Download CV ↓</a><a class="btn btn-ghost" href="{ATS_PDF}">ATS-friendly CV</a><a class="btn btn-ghost" href="contact.html">Contact →</a></div></section>
<section class="wrap sec"><div class="sec-head"><span class="eyebrow">Work experience</span><h2>Where I have worked</h2><p><b>Right now:</b> full-time Senior Odoo Developer at TTI, Odoo techno-functional consultant at Big Binary Tech, and founder of my own app studio, NeuralBytea.</p></div>{timeline(D['experience'], full=True)}</section>
<section class="wrap sec"><div class="sec-head"><span class="eyebrow">Skills</span><h2>Tools and technologies</h2></div><div class="grid fam-grid">{skills}</div></section>
<section class="wrap sec"><div class="sec-head"><span class="eyebrow">Education</span><h2>Education and certification</h2></div>
 <div class="grid fam-grid"><div class="card info"><h3>Education</h3><p><b>Bachelor of Science in Computer Science</b><br>Lahore Garrison University<br><span class="muted">Jul 2019 – Jul 2023</span></p></div>
 <div class="card info"><h3>Certification</h3><p><b>Docker Training Course for Absolute Beginners</b><br>KodeKloud<br><span class="muted">2024</span></p></div></div></section>
{cta('Want the <span class="grad">full picture?</span>', "Download my CV or send a short note about the role.", root)}"""
    return page(f"Experience | {NAME} — Senior Odoo Developer & Technical Lead | Odoo 16–20",
                f"Senior Odoo Developer, 3+ years across Odoo 16–20. Founder of NeuralBytea ({N_APPS} published Odoo apps). ERP modules, OWL, portals, payments, integrations.",
                "experience.html", "experience", body)


def contact_page() -> str:
    root = ""
    body = f"""
<section class="wrap"><div class="split reveal">
 <div class="split-l"><div class="crumb"><a href="/">Home</a> / Contact</div><span class="eyebrow" style="color:#8fd8ff">Hire me</span>
  <h1>Let’s talk about your Odoo project</h1><p class="lead">Open to a remote Odoo Technical Lead role, and to contracts. {e(HIRE['response'])}</p>
  <dl class="cinfo"><dt>Email</dt><dd><a href="mailto:{CONTACT['email']}">{CONTACT['email']}</a></dd><dt>Phone</dt><dd><a href="tel:{re.sub('[^+0-9]', '', CONTACT['phone'])}">{e(CONTACT['phone'])}</a></dd>
   <dt>LinkedIn</dt><dd><a href="{CONTACT['linkedin']}" target="_blank" rel="noopener">hammad-ali</a></dd><dt>GitHub</dt><dd><a href="{CONTACT['github']}" target="_blank" rel="noopener">4858hammad</a></dd>
   <dt>Based in</dt><dd>{e(CONTACT['location'])}, working remotely</dd><dt>Time zone</dt><dd>{e(HIRE['timezone'])}</dd></dl>
  <h3>What happens next</h3><ol class="nsteps"><li><b>You send a short note</b>The role or the problem, and your Odoo version.</li><li><b>I reply within one business day</b>With questions or a first approach.</li><li><b>We talk</b>A quick call or a short technical task, whichever helps you decide faster.</li></ol></div>
 <form class="card form split-r" action="{FORM_ACTION}" method="POST"><h2>Send a message</h2><p class="muted">I usually reply within one business day.</p>
  <label>Your name<input name="name" autocomplete="name" required placeholder="Jane Doe"></label>
  <label>Email address<input type="email" name="_replyto" autocomplete="email" required placeholder="you@company.com"></label>
  <label>Subject<input id="subject" name="subject" required placeholder="Odoo project enquiry"></label>
  <label class="grow">Message<textarea name="message" required placeholder="Tell me about the role or the project…"></textarea></label>
  <input class="hp" type="text" name="_gotcha" tabindex="-1" autocomplete="off" aria-hidden="true">
  <button class="btn btn-primary" type="submit">Send message →</button><div id="status" class="status" role="status" aria-live="polite"></div></form></div></section>
<section class="wrap sec"><div class="sec-head"><span class="eyebrow">Terms</span><h2>Rates &amp; availability</h2></div>{hire_cards()}</section>"""
    return page(f"Hire an Odoo Developer — Contact {NAME}",
                "Open to a remote Odoo Technical Lead role and Odoo contracts. Send a note about your project; replies within one business day.",
                "contact.html", "contact", body)


def privacy_page() -> str:
    chat = ("<li><b>Chat assistant:</b> the questions you type into the chat window. The conversation stays in your browser tab only (session storage) and is cleared when you close the tab.</li>" if CHAT_ON else "")
    proc = ("<li><b>Groq</b> generates the chat answers from the questions you type" + (", through a <b>Cloudflare</b> Worker that holds the access key" if CHAT_ENDPOINT else ", directly from your browser") +
            ". Do not type passwords or private data into the chat. Conversations are not stored by this site.</li>") if CHAT_ON else ""
    body = f"""
<section class="wrap doc-head"><div class="crumb"><a href="/">Home</a> / Privacy</div><h1>Privacy Policy</h1><p class="muted">Last updated {dt.date.today().strftime('%d %B %Y')}</p></section>
<section class="wrap doc"><nav class="toc" aria-label="On this page"><b>On this page</b><a href="#collect">What is collected</a><a href="#who">Who processes it</a><a href="#contact">Contact</a></nav>
<article><section id="collect"><h2>What is collected</h2><p>Only what you choose to send, plus the technical data any website receives:</p>
<ul><li><b>Contact form:</b> your name, email address, subject and message.</li>{chat}<li><b>Technical data:</b> your IP address and browser details, which the hosting provider receives when you load a page.</li></ul>
<p>This site runs no analytics or advertising trackers and sets no cookies.</p></section>
<section id="who"><h2>Who processes it</h2><ul><li><b>Formspree</b> receives the contact form and forwards it to my email inbox.</li><li><b>GitHub Pages</b> hosts this website and may keep standard server logs.</li><li><b>Google Fonts</b> serves the fonts, so your browser requests them from Google.</li>{proc}</ul>
<p>Links to the Odoo Apps Store, NeuralBytea and other sites take you away from this website. Their own privacy policies apply there.</p></section>
<section id="contact"><h2>Contact</h2><p>For questions or to ask me to delete a message you sent, email <a href="mailto:{CONTACT['email']}">{CONTACT['email']}</a>.</p></section></article></section>"""
    return page(f"Privacy Policy | {NAME}", "How this portfolio handles the data you send through the contact form and the chat assistant.", "privacy.html", "", body)


def not_found() -> str:
    redirect = """<script>(function(){var old='/hammad-ali.github.io/';if(location.pathname.indexOf(old)===0){location.replace('/'+location.pathname.slice(old.length)+location.search+location.hash);}})();</script>"""
    body = """
<section class="wrap page-hero" style="text-align:center;padding-top:96px"><span class="eyebrow">Error 404</span><h1>That page doesn't exist</h1>
 <p class="lead" style="margin:0 auto">The link may be old or mistyped. Try one of these instead.</p>
 <div class="btn-row center"><a class="btn btn-primary" href="/index.html">Home</a><a class="btn btn-ghost" href="/odoo.html">Projects</a><a class="btn btn-ghost" href="/contact.html">Contact</a></div></section>"""
    h = page(f"Page not found | {NAME}", "Page not found.", "404.html", "", body)
    h = h.replace('<meta name="robots" content="index,follow,max-image-preview:large">', '<meta name="robots" content="noindex,follow">' + redirect)
    # 404 can be served from any depth, so every link must be root-absolute
    return (h.replace('href="assets/', 'href="/assets/').replace('src="assets/', 'src="/assets/').replace('href="index.html', 'href="/index.html')
            .replace('href="odoo.html', 'href="/odoo.html').replace('href="apps.html', 'href="/apps.html').replace('href="experience.html', 'href="/experience.html')
            .replace('href="contact.html', 'href="/contact.html').replace('href="privacy.html', 'href="/privacy.html')
            .replace('href="favicon', 'href="/favicon').replace('href="apple-touch', 'href="/apple-touch'))


def redirect_pages(ids: list[str]) -> None:
    style = '<meta charset="UTF-8"><meta name="robots" content="noindex, follow">'
    write("project.html", f"""<!DOCTYPE html>
<html lang="en"><head>{style}<title>Redirecting… | {NAME}</title>
<script>(function(){{var ids={json.dumps(ids)};var id=new URLSearchParams(location.search).get('id');location.replace(ids.indexOf(id)>-1?'/projects/'+id+'/':'/odoo.html');}})();</script>
<noscript><meta http-equiv="refresh" content="0; url=/odoo.html"></noscript></head>
<body><p><a href="/odoo.html">See all projects</a></p></body></html>
""")
    for old, new, label in (("web.html", "/odoo.html", "Odoo projects"), ("android.html", "/odoo.html?line=mobile", "mobile projects")):
        write(old, f"""<!DOCTYPE html>
<html lang="en"><head>{style}<meta http-equiv="refresh" content="0; url={new}"><title>Moved | {NAME}</title></head>
<body><p>This page has moved to <a href="{new}">{label}</a>.</p></body></html>
""")


# ------------------------------------------------------------------ chat knowledge (shared by the Worker and direct mode)
def write_knowledge() -> None:
    def price(a): return "Free" if a["price"] in ("", "0") else f"${a['price']}"
    facts = [
        f"{NAME} is a Senior Odoo Developer and Technical Lead from Lahore, Pakistan, working remotely, with 3+ years of Odoo development across Odoo 16 to 20.",
        f"He founded NeuralBytea and has published {N_APPS} apps on the Odoo Apps Store (portals, payments, integrations, HR and payroll, dashboards, AI assistant, education, backend UI) for Odoo 17 to 20.",
        "He previously led a team of 3 Odoo developers and 1 functional consultant at Aetos Technologies.",
        "Scale: employee self-service for 250+ employees across 4 branches; a Mastercard Hosted Checkout provider handling about 200 payments a day; a 54,000+ record migration and backfill; about 250 orders a day and about 200 doctor and clinic portal users on ClearPath Orthodontics; a field sales portal for about 15 to 20 salespeople and 5 to 7 managers.",
        f"Hiring: rate {HIRE['rate']} ({HIRE['rate_note']}). Availability: {HIRE['availability']}. Time zone: {HIRE['timezone']} ({HIRE['timezone_note']}). Engagements: {'; '.join(HIRE['engagements'])}. {HIRE['response']}",
        "He is open to a remote Odoo Technical Lead role and to contracts.",
        "He studied BS Computer Science at Lahore Garrison University (2019 to 2023)."]
    know = {
        "PROFILE": {"name": NAME, "studio": "NeuralBytea", "site": SITE_URL + "/", "email": CONTACT["email"], "linkedin": CONTACT["linkedin"], "github": CONTACT["github"],
                    "contact_page": "/contact.html", "apps_page": NBSITE + "/apps/", "facts": facts},
        "EXPERIENCE": [{"role": x["role"], "company": x["company"], "period": x["period"]} for x in D["experience"]],
        "PROJECTS": [{"id": p["id"], "title": p["title"], "client": p.get("client", ""), "year": p.get("year"), "odoo_version": p.get("odoo_version", ""),
                      "role": p.get("role", ""), "summary": p.get("full_desc") or p.get("short_desc", ""), "highlights": p.get("highlights") or [],
                      "tags": p.get("tags") or [], "modules": p.get("modules") or [], "page": "/" + project_url(p)} for p in PROJECTS],
        "APPS": [{"id": a["id"], "name": a["name"], "line": LINE_LABEL[a["line"]], "versions": a["versions"], "price": price(a), "desc": a["desc"],
                  "url": f"{NBSITE}/apps/{a['id']}/"} for a in APPS],
    }
    js = "// GENERATED by tools/build_site.py from portfolio_data.yaml and data/apps.json. Do not edit.\n" + "\n".join(
        f"export const {k} = {json.dumps(v, indent=1, ensure_ascii=False)};" for k, v in know.items()) + "\n"
    write("worker/src/knowledge.js", js)
    if CHAT_KEY:  # direct mode: the browser imports the prompt builder
        (ROOT / "assets/chat").mkdir(parents=True, exist_ok=True)
        for f in ("prompt.js", "knowledge.js"):
            shutil.copy(ROOT / "worker/src" / f, ROOT / "assets/chat" / f)


# ------------------------------------------------------------------ main
def main() -> None:
    ordered = sorted(PROJECTS, key=lambda p: (-int(p.get("year") or 0), 0 if p.get("featured") else 1))
    write("index.html", home())
    write("odoo.html", projects_page())
    write("apps.html", apps_page())
    write("experience.html", experience_page())
    write("contact.html", contact_page())
    write("privacy.html", privacy_page())
    write("404.html", not_found())
    keep = set()
    for i, p in enumerate(PROJECTS):
        write(project_url(p) + "index.html", project_page(p, i, ordered))
        keep.add(p["id"])
    out = ROOT / "projects"
    for stale in out.iterdir():
        if stale.is_dir() and stale.name not in keep:
            shutil.rmtree(stale)
    redirect_pages(sorted(keep))
    write_knowledge()
    data_mod = lastmod(ROOT / "portfolio_data.yaml")
    urls = [(SITE_URL + "/", TODAY, "1.0"), (SITE_URL + "/odoo.html", TODAY, "0.9"), (SITE_URL + "/apps.html", TODAY, "0.9"),
            (SITE_URL + "/experience.html", TODAY, "0.9"), (SITE_URL + "/contact.html", TODAY, "0.7"), (SITE_URL + "/privacy.html", TODAY, "0.2")]
    urls += [(f"{SITE_URL}/{project_url(p)}", data_mod, "0.8" if p.get("category") == "odoo" else "0.3") for p in PROJECTS]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          "\n".join(f"  <url><loc>{u}</loc><lastmod>{m}</lastmod><priority>{pr}</priority></url>" for u, m, pr in urls) + "\n</urlset>\n")
    print(f"Built {len(PROJECTS)} project pages + 7 pages, {N_APPS} apps, sitemap with {len(urls)} URLs. Chat: "
          f"{'worker endpoint' if CHAT_ENDPOINT else ('direct (CI key)' if CHAT_KEY else 'off')}")


if __name__ == "__main__":
    main()
