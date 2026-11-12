#!/usr/bin/env python3
"""Build static, crawlable pages from portfolio_data.yaml.

What it does (idempotent; safe to run on every push):
  1. Writes one real HTML page per project to  projects/<id>/index.html
     -> unique <title>, description, canonical, Open Graph and JSON-LD in the
        raw HTML, so Google, LinkedIn, WhatsApp and Slack previews all see the
        real case study instead of the "Project Title" placeholder.
  2. Rewrites project.html as a tiny redirect so old ?id= links keep working.
  3. Injects the same static navigation and footer into every top-level page,
     so links exist even before (or without) JavaScript.
  4. Regenerates sitemap.xml from the data, so it can never list a project
     that does not exist or miss one that does.

Usage:  pip install pyyaml && python tools/build_pages.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = yaml.safe_load((ROOT / "portfolio_data.yaml").read_text(encoding="utf-8"))
SITE = DATA["site"]["url"].rstrip("/")            # https://4858hammad.github.io
NAME = DATA["site"]["name"]
OG_IMAGE = f"{SITE}/assets/images/og-cover.png"
_VIS = ROOT / "tools" / "visuals.yaml"
VISUALS = yaml.safe_load(_VIS.read_text(encoding="utf-8")) if _VIS.exists() else {}
FONTS = ("https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400..800"
         "&family=Syne:wght@400..800&display=swap")

# Top-level pages: (file, nav label or None if not in the menu, sitemap priority or None to omit)
PAGES = [
    ("index.html", "Home", "1.0"),
    ("odoo.html", "Odoo ERP", "0.9"),
    ("apps.html", "Apps", "0.9"),
    ("android.html", "Android", "0.4"),
    ("experience.html", "Experience", "0.9"),
    ("contact.html", "Contact", "0.7"),
    ("web.html", None, None),        # empty page: kept only as a redirect, never listed
    ("project.html", None, None),    # legacy template: now a redirect, never listed
]
CATEGORY = {"odoo": ("Odoo ERP Projects", "odoo.html"),
            "android": ("Android Projects", "android.html")}

e = lambda v: html.escape(str(v if v is not None else ""), quote=True)  # noqa: E731


def lastmod(path: Path) -> str:
    """Last commit date of a file (falls back to today when not in git)."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return out or dt.date.today().isoformat()
    except Exception:
        return dt.date.today().isoformat()


# ---------------------------------------------------------------- shared chrome
def nav_html(active: str, prefix: str = "") -> str:
    """Static header/nav. `prefix` makes links work from /projects/<id>/ pages."""
    initials = "".join(p[0] for p in NAME.split())[:2]
    cur = ' class="active" aria-current="page"'
    links = "".join(
        f'<a href="{prefix}{f}"{cur if f == active else ""}>{e(label)}</a>'
        for f, label, _ in PAGES if label)
    avail = DATA["site"].get("available_for_work", True)
    return (f'<header class="site-header"><nav class="nav" aria-label="Main">'
            f'<a href="{prefix}index.html" class="nav-logo"><span class="logo-mark">{e(initials)}</span>{e(NAME)}</a>'
            f'<button class="nav-toggle" type="button" aria-label="Toggle menu" aria-expanded="false">☰</button>'
            f'<div class="nav-links">{links}</div>'
            f'<div class="pill{"" if avail else " not-avail"}">{"Open to work" if avail else "Unavailable"}</div>'
            f'</nav></header>')


def footer_html() -> str:
    c = DATA["contact"]
    return (f'<span>{e(NAME)} · Odoo Developer · {e(c["location"])}</span>'
            f'<span>© {dt.date.today().year} {e(NAME)}</span>')


NAV_TOGGLE_JS = ("<script>document.querySelectorAll('.nav-toggle').forEach(function(t){"
                 "t.addEventListener('click',function(){var n=t.closest('.nav'),o=n.classList.toggle('open');"
                 "t.setAttribute('aria-expanded',String(o));t.textContent=o?'✕':'☰';});});</script>")


# ---------------------------------------------------------------- project pages
def project_url(p: dict) -> str:
    return f"{SITE}/projects/{p['id']}/"


def project_page(p: dict, prev_p: dict | None, next_p: dict | None) -> str:
    cat_name, cat_file = CATEGORY.get(p["category"], ("Projects", "odoo.html"))
    version = f" — {p['odoo_version']}" if p.get("odoo_version") else ""
    title = f"{p['title']}{version} Case Study | {NAME}"
    desc = p.get("short_desc", "")
    url = project_url(p)
    img = f"/{p['image']}" if p.get("image") else ""
    # per-project link preview (tools/build_visuals.py) when it exists, else the site cover
    og_file = ROOT / "assets" / "images" / "og" / f"{p['id']}.png"
    og_image = f"{SITE}/assets/images/og/{p['id']}.png" if og_file.exists() else OG_IMAGE
    flow = VISUALS.get(p["id"], {}).get("flow") or []
    alt = (f"Solution diagram of {p['title']}: " + " → ".join(s["label"] for s in flow)) if flow \
        else f"{p['title']} — project illustration"
    tags = "".join(f'<span class="dtg">{e(t)}</span>' for t in p.get("tags") or [])
    highlights = "".join(f"<li>{e(h)}</li>" for h in p.get("highlights") or [])
    modules = "".join(f'<span class="mod-tag">{e(m)}</span>' for m in p.get("modules") or [])
    stack = "".join(f'<span class="mod-tag">{e(t)}</span>' for t in p.get("tech_stack") or [])
    banner = f'<img src="{e(img)}" alt="{e(alt)}" width="1200" height="400">' if img else ""
    shots = "".join(
        f'<figure class="shot"><a href="/{e(sh["src"])}"><img src="/{e(sh["src"])}" alt="{e(sh.get("caption") or p["title"])}" '
        f'loading="lazy"></a>{"<figcaption>" + e(sh["caption"]) + "</figcaption>" if sh.get("caption") else ""}</figure>'
        for sh in p.get("screenshots") or [])
    shots = f'<h2 class="sec-lbl">Screens</h2><div class="shots">{shots}</div>' if shots else ""
    nb = ""
    if p.get("nb_app"):
        nb = (f'<h2 class="sec-lbl">Also available as a NeuralBytea app</h2><p class="detail-text">A marketplace edition '
              f'is published as <a href="https://neuralbytea.github.io/apps/{e(p["nb_app"]["id"])}/" rel="noopener">'
              f'{e(p["nb_app"]["name"])}</a>.</p>')
    prev_link = (f'<a class="nf-btn" rel="prev" href="../{e(prev_p["id"])}/">← {e(prev_p["title"])}</a>'
                 if prev_p else '<span></span>')
    next_link = (f'<a class="nf-btn" rel="next" href="../{e(next_p["id"])}/">{e(next_p["title"])} →</a>'
                 if next_p else '<span></span>')
    version_block = (f'<div class="info-block"><div class="info-label">Odoo version</div>'
                     f'<div class="info-val">{e(p["odoo_version"])}</div></div>' if p.get("odoo_version") else "")
    modules_block = (f'<div class="info-block"><div class="info-label">Modules used</div>'
                     f'<div class="mod-list">{modules}</div></div>' if modules else "")
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": cat_name, "item": f"{SITE}/{cat_file}"},
                {"@type": "ListItem", "position": 3, "name": p["title"], "item": url}]},
            {"@type": "CreativeWork", "name": p["title"], "description": desc, "url": url,
             "dateCreated": str(p.get("year", "")),
             "author": {"@type": "Person", "@id": f"{SITE}/#person", "name": NAME},
             "keywords": ", ".join(p.get("tags") or [])},
        ],
    }
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}">
  <link rel="canonical" href="{url}">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <meta name="author" content="{e(NAME)}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{e(NAME)}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{e(title)}">
  <meta name="twitter:description" content="{e(desc)}">
  <meta name="twitter:image" content="{og_image}">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{FONTS}">
  <link rel="stylesheet" href="/assets/style.css">
  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <div class="container">
    {nav_html(active=cat_file, prefix="/")}
    <main id="main">
      <article class="detail-wrap">
        <div class="detail-main">
          <div class="proj-banner">{banner}</div>
          <div class="detail-content">
            <a class="back-link" href="/{cat_file}">← Back to <em>{e(cat_name)}</em></a>
            <h1 class="detail-title">{e(p["title"])}</h1>
            <p class="detail-sub">{e(p.get("client", ""))} · {e(p.get("year", ""))} · {e(cat_name.replace(" Projects", ""))}</p>
            <div class="detail-tags">{tags}</div>
            <h2 class="sec-lbl">About this project</h2>
            <p class="detail-text">{e(p.get("full_desc") or desc)}</p>
            {"<h2 class='sec-lbl'>Key features / deliverables</h2><ul class='feat-list'>" + highlights + "</ul>" if highlights else ""}
            {shots}
            {nb}
          </div>
        </div>
        <aside class="sidebar" aria-label="Project facts">
          <div class="info-block"><div class="info-label">Client</div><div class="info-val">{e(p.get("client", ""))}</div></div>
          <div class="info-block"><div class="info-label">Year</div><div class="info-val">{e(p.get("year", ""))}</div></div>
          {version_block}
          <div class="info-block"><div class="info-label">Role</div><div class="info-val muted">{e(p.get("role", "Developer"))}</div></div>
          {modules_block}
          <div class="info-block"><div class="info-label">Tech stack</div><div class="mod-list">{stack}</div></div>
          <div class="info-block"><a class="btn-primary" href="/contact.html" style="width:100%;justify-content:center;">Discuss a similar project</a></div>
        </aside>
      </article>
      <nav class="nav-footer" aria-label="More projects">{prev_link}{next_link}</nav>
    </main>
    <footer class="footer">{footer_html()}</footer>
  </div>
  {NAV_TOGGLE_JS}
</body>
</html>
"""


def legacy_redirect(valid_ids: list[str]) -> str:
    """project.html?id=x  ->  /projects/x/   (unknown ids go to the listing)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="robots" content="noindex, follow">
  <title>Redirecting… | {e(NAME)}</title>
  <script>
    (function () {{
      var ids = {json.dumps(valid_ids)};
      var id = new URLSearchParams(location.search).get('id');
      location.replace(ids.indexOf(id) > -1 ? '/projects/' + id + '/' : '/odoo.html');
    }})();
  </script>
  <noscript><meta http-equiv="refresh" content="0; url=/odoo.html"></noscript>
</head>
<body><p><a href="/odoo.html">See all projects</a></p></body>
</html>
"""


WEB_REDIRECT = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="robots" content="noindex, follow">
  <meta http-equiv="refresh" content="0; url=/odoo.html">
  <title>Moved | {e(NAME)}</title>
</head>
<body><p>This page has moved to <a href="/odoo.html">Odoo projects</a>.</p></body>
</html>
"""


# ---------------------------------------------------------------- inject chrome
NAV_RE = re.compile(r'<div id="nav-container">.*?</div><!-- /nav -->|<div id="nav-container"></div>', re.S)
FOOT_RE = re.compile(r'<footer class="footer" id="footer-container">.*?</footer><!-- /footer -->|'
                     r'<div class="footer" id="footer-container"></div>', re.S)


def inject_chrome(file: str) -> None:
    path = ROOT / file
    src = path.read_text(encoding="utf-8")
    out = NAV_RE.sub(lambda _: f'<div id="nav-container">{nav_html(file)}</div><!-- /nav -->', src, count=1)
    out = FOOT_RE.sub(lambda _: f'<footer class="footer" id="footer-container">{footer_html()}</footer><!-- /footer -->',
                      out, count=1)
    if out != src:
        path.write_text(out, encoding="utf-8")


# ---------------------------------------------------------------- main
def main() -> None:
    projects = DATA["projects"]
    by_cat: dict[str, list[dict]] = {}
    for p in sorted(projects, key=lambda p: -int(p.get("year") or 0)):   # stable: newest year first
        by_cat.setdefault(p["category"], []).append(p)

    out_dir = ROOT / "projects"
    keep = set()
    for plist in by_cat.values():
        for i, p in enumerate(plist):
            d = out_dir / p["id"]
            d.mkdir(parents=True, exist_ok=True)
            page = project_page(p, plist[i - 1] if i else None, plist[i + 1] if i + 1 < len(plist) else None)
            page = re.sub(r"\n[ \t]*(?=\n)", "", page)      # drop blank lines left by empty optional blocks
            (d / "index.html").write_text(page, encoding="utf-8")
            keep.add(p["id"])
    for stale in out_dir.iterdir():                     # remove pages for deleted projects
        if stale.is_dir() and stale.name not in keep:
            for f in stale.iterdir():
                f.unlink()
            stale.rmdir()

    (ROOT / "project.html").write_text(legacy_redirect(sorted(keep)), encoding="utf-8")
    (ROOT / "web.html").write_text(WEB_REDIRECT, encoding="utf-8")
    for f, label, _ in PAGES:
        if label:
            inject_chrome(f)

    data_mod = lastmod(ROOT / "portfolio_data.yaml")
    urls = [(f"{SITE}/" if f == "index.html" else f"{SITE}/{f}", lastmod(ROOT / f), pr)
            for f, _, pr in PAGES if pr]
    urls += [(project_url(p), data_mod, "0.8" if p["category"] == "odoo" else "0.3")
             for p in projects]
    body = "\n".join(f"  <url><loc>{u}</loc><lastmod>{m}</lastmod><priority>{pr}</priority></url>"
                     for u, m, pr in urls)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "\n</urlset>\n",
        encoding="utf-8")
    print(f"Built {len(keep)} project pages, sitemap with {len(urls)} URLs.")


if __name__ == "__main__":
    main()
