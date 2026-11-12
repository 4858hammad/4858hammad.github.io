#!/usr/bin/env python3
"""Render a solution-diagram PNG for every project in tools/visuals.yaml.

Writes, per project id:
  assets/images/projects/<id>.png   banner, 1200x400 layout saved at 1.5x (1800x600) for sharp retina display
  assets/images/og/<id>.png         link preview for LinkedIn / WhatsApp / X, 1200x630

The pictures are diagrams of how each system works, drawn only from the facts in
portfolio_data.yaml + tools/visuals.yaml. They are labelled "Solution diagram"
so nobody mistakes them for screenshots of a client's system.

Run locally (not in CI: it needs a browser), then commit the PNGs:
    pip install pyyaml playwright pillow
    python -m playwright install chromium        # once
    python tools/build_visuals.py                # all projects
    python tools/build_visuals.py mastercard-payment   # just one
Set CHROME_PATH to use an installed Chrome instead of Playwright's Chromium.
"""
from __future__ import annotations

import html
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DATA = yaml.safe_load((ROOT / "portfolio_data.yaml").read_text(encoding="utf-8"))
SPECS = yaml.safe_load((TOOLS / "visuals.yaml").read_text(encoding="utf-8"))
PROJECTS = {p["id"]: p for p in DATA["projects"]}
NAME = DATA["site"]["name"]
SITE = DATA["site"]["url"].replace("https://", "").rstrip("/")
OUT_BANNER = ROOT / "assets" / "images" / "projects"
OUT_OG = ROOT / "assets" / "images" / "og"

e = lambda v: html.escape(str(v if v is not None else ""))  # noqa: E731

CSS = """
@font-face { font-family: 'DM Sans'; src: url('fonts/dm-sans-latin-wght-normal.woff2') format('woff2');
  font-weight: 100 1000; }
@font-face { font-family: 'Syne'; src: url('fonts/syne-latin-700-normal.woff2') format('woff2'); font-weight: 700; }
@font-face { font-family: 'Syne'; src: url('fonts/syne-latin-800-normal.woff2') format('woff2'); font-weight: 800; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DM Sans', sans-serif; color: #F0F2F5; -webkit-font-smoothing: antialiased; }
.frame { position: relative; overflow: hidden;
  background:
    radial-gradient(700px 380px at 82% 8%, rgba(91,141,239,.22), transparent 70%),
    radial-gradient(520px 320px at 8% 100%, rgba(34,211,238,.12), transparent 70%),
    linear-gradient(135deg, #16204A 0%, #0B1226 100%); }
.frame > * { position: relative; }
.chip { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 999px;
  font-size: 13px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: #D5DCFF; background: rgba(139,155,255,.12); border: 1px solid rgba(139,155,255,.35); }
.tag { position: absolute; top: 22px; right: 26px; font-size: 12px; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; color: #8F9BC4; }
.metric { font-family: 'DM Sans', sans-serif; font-weight: 800; letter-spacing: -.03em; line-height: 1.05;
  white-space: nowrap; overflow: hidden; padding-bottom: 4px;
  background: linear-gradient(100deg, #8B9BFF 0%, #22D3EE 100%); -webkit-background-clip: text; color: transparent; }
.mlabel { color: #AEB9D6; }
/* flow */
.flow { display: flex; align-items: stretch; width: 100%; }
.node { flex: 1 1 0; min-width: 0; border-radius: 14px; padding: 14px 14px 13px; display: flex; flex-direction: column;
  justify-content: center; gap: 5px; text-align: center; }
.node .lbl { font-weight: 700; line-height: 1.18; padding: 0 3px; }
.node .sub { color: #AEB9D6; line-height: 1.25; padding: 0 3px; }
.node ul { list-style: none; display: flex; flex-direction: column; gap: 4px; margin-top: 3px; }
.node li { border-radius: 7px; padding: 4px 6px; background: rgba(255,255,255,.06); color: #DCE2F5; line-height: 1.2; }
.k-odoo { background: rgba(139,155,255,.16); border: 1.5px solid rgba(139,155,255,.75); }
.k-ext  { background: rgba(255,255,255,.04); border: 1.5px solid rgba(174,185,214,.45); }
.k-user { background: rgba(255,255,255,.03); border: 1.5px dashed rgba(174,185,214,.6); }
.k-out  { background: rgba(34,211,238,.12); border: 1.5px solid rgba(34,211,238,.8); }
.link { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; }
.link svg { display: block; }
.link .ll { font-weight: 700; color: #D5DCFF; white-space: nowrap; letter-spacing: .02em; }
.legend { display: flex; gap: 18px; color: #8F9BC4; font-size: 12px; font-weight: 600; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 14px; height: 10px; border-radius: 3px; display: inline-block; }
.facts { display: flex; gap: 10px; flex-wrap: wrap; }
.fact { padding: 8px 14px; border-radius: 10px; background: rgba(255,255,255,.05); border: 1px solid rgba(148,163,214,.25);
  font-size: 17px; font-weight: 600; color: #E7EBF8; }
"""

LEGEND = ('<div class="legend"><span><i class="k-odoo"></i>Built in Odoo</span>'
          '<span><i class="k-ext"></i>External system</span><span><i class="k-user"></i>Person</span>'
          '<span><i class="k-out"></i>Result</span></div>')


def wbr(text: str) -> str:
    """Escape, and let dotted identifiers (payment.transaction) wrap after the dot."""
    return re.sub(r"(?<=[a-z])\.(?=[a-z])", ".<wbr>", e(text))


def arrow(two_way: bool, w: int) -> str:
    head = '<path d="M{x} 7 l-8 -6 v12 z" fill="#8B9BFF"/>'.format(x=w)
    tail = '<path d="M0 7 l8 -6 v12 z" fill="#8B9BFF"/>' if two_way else ""
    return (f'<svg width="{w}" height="14" viewBox="0 0 {w} 14">'
            f'<line x1="{4 if two_way else 0}" y1="7" x2="{w - 4}" y2="7" stroke="#8B9BFF" stroke-width="2.5"/>'
            f'{tail}{head}</svg>')


def flow_html(spec: dict, size: dict) -> str:
    steps, links = spec["flow"], spec.get("links") or [{} for _ in spec["flow"][1:]]
    parts = []
    for i, s in enumerate(steps):
        items = "".join(f"<li>{e(x)}</li>" for x in s.get("items") or [])
        parts.append(
            f'<div class="node k-{e(s["kind"])}" style="padding:{size["pad"]}px">'
            f'<div class="lbl" style="font-size:{size["lbl"]}px">{e(s["label"])}</div>'
            + (f'<div class="sub" style="font-size:{size["sub"]}px">{wbr(s["sub"])}</div>' if s.get("sub") else "")
            + (f'<ul style="font-size:{size["sub"]}px">{items}</ul>' if items else "")
            + "</div>")
        if i < len(steps) - 1:
            lk = links[i] or {}
            fs = min(size["sub"] - 2, 14)
            # each gap is as wide as its own label needs, so a label never runs over a box
            gw = max(size["gap"], int(len(lk.get("label") or "") * fs * 0.62) + 18)
            label = f'<div class="ll" style="font-size:{fs}px">{e(lk["label"])}</div>' if lk.get("label") else ""
            parts.append(f'<div class="link" style="width:{gw}px">{label}'
                         f'{arrow(lk.get("type") == "<->", gw - 10)}</div>')
    return f'<div class="flow">{"".join(parts)}</div>'


def sizes(spec: dict, wide: bool) -> dict:
    n = len(spec["flow"])
    gap = 46 if n >= 5 else 58
    if wide:   # link preview: the flow spans the full 1096 px width
        return {"lbl": 22 if n >= 5 else 24, "sub": 15 if n >= 5 else 16, "pad": 12 if n >= 5 else 15, "gap": gap}
    # banner: big type because cards show it at a third of its size; the fitter shrinks what doesn't fit
    return {"lbl": 23 if n >= 5 else 27, "sub": 16 if n >= 5 else 18, "pad": 12 if n >= 5 else 16, "gap": gap}
    return base


def banner_html(p: dict, spec: dict) -> str:
    version = p.get("odoo_version") or "Odoo"
    return f"""<div class="frame" style="width:1200px;height:400px;display:flex;align-items:center;gap:30px;padding:0 40px 0 44px">
  <div class="tag">Solution diagram</div>
  <div style="flex:0 0 250px;min-width:0;display:flex;flex-direction:column;gap:14px">
    <div><span class="chip">{e(version)}</span></div>
    <div class="metric fit" style="font-size:92px">{e(p.get('metric', ''))}</div>
    <div class="mlabel" style="font-size:21px;line-height:1.3">{e(p.get('metric_label', ''))}</div>
  </div>
  <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:20px;padding-top:30px">
    {flow_html(spec, sizes(spec, False))}
    {LEGEND}
  </div>
</div>"""


def og_html(p: dict, spec: dict) -> str:
    version = p.get("odoo_version") or "Odoo"
    # the header chip already names the version, so a fact that only repeats it is dropped
    facts = "".join(f'<div class="fact">{e(f)}</div>' for f in spec.get("facts") or []
                    if f.replace(" ", "") != str(version).replace(" ", ""))
    return f"""<div class="frame" style="width:1200px;height:630px;display:flex;flex-direction:column;padding:44px 52px 36px">
  <div class="tag">Solution diagram</div>
  <div><span class="chip">Odoo case study · {e(version)}</span></div>
  <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:46px;line-height:1.08;letter-spacing:-.02em;margin-top:18px;max-width:1010px">{e(p['title'])}</div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:16px">
    {flow_html(spec, sizes(spec, True))}
  </div>
  <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:24px">
    <div style="display:flex;align-items:center;gap:22px">
      <div class="metric fit" style="font-size:60px;max-width:300px">{e(p.get('metric', ''))}</div>
      <div class="facts">{facts}</div>
    </div>
  </div>
  <div style="margin-top:18px;padding-top:14px;border-top:1px solid rgba(148,163,214,.2);display:flex;justify-content:space-between;color:#AEB9D6;font-size:16px;font-weight:600">
    <span>{e(NAME)} · Senior Odoo Developer</span><span>{e(SITE)}</span>
  </div>
</div>"""


def page(body: str) -> str:
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


FITTER_JS = """() => {
  const shrink = (el, kids, min, widthOnly) => { let guard = 60;
    while ((el.scrollWidth > el.clientWidth + 1 || (!widthOnly && el.scrollHeight > el.clientHeight + 1)) && guard--) {
      let changed = false;
      for (const k of kids) { const fs = parseFloat(getComputedStyle(k).fontSize);
        if (fs > min) { k.style.fontSize = (fs - 1) + 'px'; changed = true; } }
      if (!changed) break; } };
  document.querySelectorAll('.metric.fit').forEach(m => shrink(m, [m], 28, true));
  // a box is too tight when any line inside it is wider than its own column, or the box overflows
  document.querySelectorAll('.node').forEach(n => {
    const kids = n.querySelectorAll('.lbl, .sub, ul'); let guard = 60;
    const textW = el => { const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect().width; };
    const tight = () => [...n.querySelectorAll('.lbl, .sub, li')].some(k => textW(k) > k.clientWidth - 8)
                        || n.scrollHeight > n.clientHeight + 1;
    while (tight() && guard--) {
      let changed = false;
      for (const k of kids) { const fs = parseFloat(getComputedStyle(k).fontSize);
        if (fs > 12) { k.style.fontSize = (fs - 1) + 'px'; changed = true; } }
      if (!changed) break; } });
}"""
OVERFLOW_JS = """() => [...document.querySelectorAll('.node, .fact, .flow, .metric')]
  .filter(n => n.scrollWidth > n.clientWidth + 1 || (!n.classList.contains('metric') && n.scrollHeight > n.clientHeight + 1))
  .map(n => n.className + ': ' + n.innerText.slice(0, 40).replace(/\\n/g, ' '))"""
FIT_JS = """() => { const f = document.querySelector('.frame'), r = f.getBoundingClientRect();
  return [...f.querySelectorAll('*')].filter(n => { const b = n.getBoundingClientRect();
    return b.width && (b.right > r.right + 0.5 || b.bottom > r.bottom + 0.5); }).length; }"""


def render(ids: list[str]) -> list[str]:
    problems = []
    OUT_BANNER.mkdir(parents=True, exist_ok=True)
    OUT_OG.mkdir(parents=True, exist_ok=True)
    launch = {"executable_path": os.environ["CHROME_PATH"]} if os.environ.get("CHROME_PATH") else {}
    with sync_playwright() as pw, tempfile.TemporaryDirectory(dir=TOOLS) as tmp:
        browser = pw.chromium.launch(**launch)
        for pid in ids:
            p, spec = PROJECTS[pid], SPECS[pid]
            for kind, html_doc, (w, h), scale, out in (
                ("banner", banner_html(p, spec), (1200, 400), 1.5, OUT_BANNER / f"{pid}.png"),
                ("og", og_html(p, spec), (1200, 630), 1, OUT_OG / f"{pid}.png"),
            ):
                f = Path(tmp) / f"{pid}-{kind}.html"
                f.write_text(page(html_doc).replace("url('fonts/", f"url('{(TOOLS / 'fonts').as_uri()}/"),
                             encoding="utf-8")
                pg = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
                pg.goto(f.as_uri())
                pg.evaluate("document.fonts.ready.then(() => document.fonts.size)")
                pg.evaluate(FITTER_JS)
                for issue in pg.evaluate(OVERFLOW_JS):
                    problems.append(f"{pid} [{kind}] text overflows: {issue}")
                if pg.evaluate(FIT_JS):
                    problems.append(f"{pid} [{kind}] content runs past the frame")
                pg.locator(".frame").screenshot(path=str(out))
                pg.close()
                img = Image.open(out).convert("RGB")
                img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(
                    out, optimize=True)
        browser.close()
    return problems


def main() -> None:
    ids = sys.argv[1:] or [pid for pid in SPECS if pid in PROJECTS]
    unknown = [i for i in ids if i not in SPECS or i not in PROJECTS]
    if unknown:
        sys.exit(f"No spec or project for: {', '.join(unknown)}")
    problems = render(ids)
    print(f"Rendered {len(ids)} projects -> {OUT_BANNER.relative_to(ROOT)}/ and {OUT_OG.relative_to(ROOT)}/")
    if problems:
        print("Check these layouts:\n  " + "\n  ".join(problems))
        sys.exit(1)


if __name__ == "__main__":
    main()
