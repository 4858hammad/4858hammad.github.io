#!/usr/bin/env python3
"""Generate one illustrative banner SVG per project.

Reads portfolio_data.yaml (title, category, odoo_version, metric, metric_label)
and writes assets/images/<project-id>.svg, then points each project's `image:`
line at its SVG. Re-run after changing a metric or adding a project:

    python3 build_covers.py

The banners are diagrams, not screenshots of client systems, so they carry no
client data. Layout contract (the CSS depends on it): 1200x400, the metric and
label live in the left ~30% (the narrow listing thumbnail crops to that zone),
the diagram lives on the right.
"""
import re
from html import escape
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "portfolio_data.yaml"
OUT = ROOT / "assets" / "images"
W, H = 1200, 400
FONT = "'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

BG = {
    "odoo": ("#16204A", "#0B1226"),
    "android": ("#103425", "#0A1210"),
    "web": ("#2A1A50", "#0E0A1E"),
}

ACCENTS = {
    "dashboard": ("#8B7CF6", "#22D3EE"),
    "portal": ("#5B8DEF", "#22D3EE"),
    "flow": ("#A78BFA", "#38BDF8"),
    "chain": ("#8B7CF6", "#34D399"),
    "payment": ("#6EA8FE", "#22D3EE"),
    "migration": ("#A78BFA", "#22D3EE"),
    "bom": ("#5B8DEF", "#A78BFA"),
    "mobile": ("#34D399", "#22D3EE"),
    "report": ("#8B7CF6", "#38BDF8"),
}

# kind + per-project diagram labels. Everything else comes from the YAML.
SPECS = {
    "tti-employee-portal": dict(kind="portal"),
    "tti-attendance-dashboard": dict(kind="dashboard"),
    "field-sales-person": dict(kind="portal"),
    "tti-loan-management": dict(kind="dashboard"),
    "tti-certification-integration": dict(kind="flow", sources=["Certification platform"], target="Odoo", both=True),
    "tti-crm-lead-integration": dict(kind="flow", sources=["Website", "GoHighLevel", "Web forms"], target="Odoo CRM", both=False),
    "tti-ai-connector": dict(kind="flow", sources=["Claude"], target="Odoo", both=True),
    "tti-payroll-reporting": dict(kind="report"),
    "tti-helpdesk-portal": dict(kind="portal"),
    "tti-biometric-attendance": dict(kind="chain", steps=["ZK device", "WDMS sync", "Attendance", "Board"]),
    "tti-partner-api": dict(kind="flow", sources=["Partner chatbot"], target="Odoo", both=True),
    "tti-crm-visit-api": dict(kind="flow", sources=["TTI CRM"], target="Odoo", both=False),
    "clearpath-orthodontics": dict(kind="chain", steps=["Doctor portal", "Advance payment", "Manufacturing", "Delivery"]),
    "mastercard-payment": dict(kind="payment"),
    "sage-integration": dict(kind="flow", sources=["Sage"], target="Odoo", both=True),
    "axis-marketing": dict(kind="flow", sources=["Meta Ads", "Web forms"], target="Odoo CRM", both=False),
    "pavo-oms": dict(kind="mobile", target="Odoo"),
    "pgi-erp-customization": dict(kind="chain", steps=["Git push", "CI/CD", "Ubuntu + Nginx", "Odoo 18"]),
    "silicon-signs-erp": dict(kind="bom", root="Product BOM", children=["Component A", "Sub-assembly", "Component B"], leaves=["v1", "v2 diff", "v1"]),
    "ringfree-integration": dict(kind="chain", steps=["Usage API", "Metered billing", "Monthly invoice", "Bank sync"]),
    "fell-erp": dict(kind="report"),
    "hrms-migration": dict(kind="migration", left="Odoo 16", right="Odoo 17"),
    "showroom-app": dict(kind="mobile", target="Firebase"),
    "idea-pitching": dict(kind="mobile", target="Firebase"),
}


def esc(s):
    return escape(str(s), quote=True)


def wrap(text, n):
    words = text.split()
    if len(text) <= n or len(words) < 2:
        return [text]
    i = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
    return [" ".join(words[:i]), " ".join(words[i:])]


def text(x, y, s, size=15, fill="#DCE3FA", weight=600, anchor="middle"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>'


def box(x, y, w, h, label, grad=False, size=15):
    fill = 'url(#g)' if grad else '#FFFFFF'
    fo = "1" if grad else ".06"
    tcolor = "#071022" if grad else "#DCE3FA"
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" fill-opacity="{fo}" stroke="#94A3D6" stroke-opacity=".25"/>'
    lines = wrap(label, max(6, int((w - 24) / (size * 0.6))))
    lh = size + 4
    y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + size * 0.35
    for i, ln in enumerate(lines):
        s += text(x + w / 2, round(y0 + i * lh, 1), ln, size=size, fill=tcolor, weight=700 if grad else 600)
    return s


def window(x, y, w, h):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#0A0F20" fill-opacity=".92" stroke="#94A3D6" stroke-opacity=".22"/>'
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        s += f'<circle cx="{x + 22 + i * 18}" cy="{y + 20}" r="5" fill="{c}"/>'
    s += f'<line x1="{x}" y1="{y + 40}" x2="{x + w}" y2="{y + 40}" stroke="#94A3D6" stroke-opacity=".16"/>'
    return s


def arrow(x1, y1, x2, y2, both=False, dashed=True):
    ms = ' marker-start="url(#ar)"' if both else ""
    dash = ' stroke-dasharray="6 6"' if dashed else ""
    # Solid colour on purpose: an objectBoundingBox gradient on a perfectly
    # horizontal line has a zero-height box and renders nothing.
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="currentColor" stroke-width="2.5"{dash} marker-end="url(#ar)"{ms}/>'


def dashboard(spec):
    s = window(430, 50, 720, 300)
    widths = [74, 58, 86, 66]
    for i in range(4):
        x = 452 + i * 172
        s += f'<rect x="{x}" y="104" width="160" height="66" rx="10" fill="#fff" fill-opacity=".05" stroke="#94A3D6" stroke-opacity=".18"/>'
        s += f'<rect x="{x + 14}" y="118" width="58" height="6" rx="3" fill="#fff" fill-opacity=".28"/>'
        s += f'<rect x="{x + 14}" y="136" width="{widths[i]}" height="18" rx="5" fill="url(#g)"/>'
    heights = [40, 68, 54, 92, 64, 104, 80, 112, 74, 96, 120, 88]
    base = 334
    pts = []
    for i, hh in enumerate(heights):
        x = 452 + i * 56
        s += f'<rect x="{x}" y="{base - hh}" width="30" height="{hh}" rx="5" fill="url(#g)" fill-opacity=".8"/>'
        pts.append(f"{x + 15},{base - hh - 12}")
    s += f'<polyline points="{" ".join(pts)}" fill="none" stroke="#fff" stroke-opacity=".7" stroke-width="2"/>'
    for p in pts:
        cx, cy = p.split(",")
        s += f'<circle cx="{cx}" cy="{cy}" r="3.5" fill="#fff"/>'
    s += f'<line x1="452" y1="{base}" x2="1128" y2="{base}" stroke="#94A3D6" stroke-opacity=".25"/>'
    return s


def portal(spec):
    s = window(430, 50, 720, 300)
    for i in range(5):
        y = 108 + i * 44
        fill = 'url(#g)' if i == 0 else "#FFFFFF"
        fo = "1" if i == 0 else ".07"
        s += f'<rect x="452" y="{y}" width="112" height="28" rx="8" fill="{fill}" fill-opacity="{fo}"/>'
    pills = ["#22D3EE", "#34D399", "#8B7CF6", "#34D399", "#22D3EE"]
    for i in range(5):
        y = 104 + i * 48
        s += f'<rect x="588" y="{y}" width="540" height="40" rx="10" fill="#fff" fill-opacity=".045" stroke="#94A3D6" stroke-opacity=".14"/>'
        s += f'<circle cx="612" cy="{y + 20}" r="13" fill="url(#g)" fill-opacity=".85"/>'
        s += f'<rect x="638" y="{y + 11}" width="{150 + (i % 3) * 30}" height="7" rx="3.5" fill="#fff" fill-opacity=".4"/>'
        s += f'<rect x="638" y="{y + 24}" width="{96 + (i % 2) * 24}" height="5" rx="2.5" fill="#fff" fill-opacity=".18"/>'
        s += f'<rect x="1040" y="{y + 11}" width="70" height="18" rx="9" fill="{pills[i]}" fill-opacity=".28" stroke="{pills[i]}" stroke-opacity=".6"/>'
    return s


def flow(spec):
    srcs = spec["sources"]
    n = len(srcs)
    s = ""
    gap = 78
    total = n * 58 + (n - 1) * (gap - 58)
    top = 200 - total / 2
    for i, label in enumerate(srcs):
        y = round(top + i * gap)
        s += box(450, y, 220, 58, label)
        s += arrow(672, y + 29, 872, 200, both=spec.get("both", False))
    s += box(880, 155, 240, 90, spec["target"], grad=True, size=22)
    return s


def chain(spec):
    steps = spec["steps"]
    n = len(steps)
    gap = 44
    w = int((700 - (n - 1) * gap) / n)
    s = ""
    for i, label in enumerate(steps):
        x = 440 + i * (w + gap)
        last = i == n - 1
        s += box(x, 155, w, 90, label, grad=last, size=16)
        s += f'<circle cx="{x + w / 2}" cy="128" r="13" fill="#fff" fill-opacity=".08" stroke="#94A3D6" stroke-opacity=".3"/>'
        s += text(x + w / 2, 133, i + 1, size=13, fill="#DCE3FA", weight=700)
        if not last:
            s += arrow(x + w + 6, 200, x + w + gap - 6, 200, dashed=False)
    return s


def payment(spec):
    s = '<rect x="450" y="135" width="210" height="130" rx="16" fill="url(#g)" fill-opacity=".95"/>'
    s += '<rect x="470" y="157" width="34" height="26" rx="5" fill="#071022" fill-opacity=".35"/>'
    s += '<circle cx="610" cy="238" r="16" fill="#071022" fill-opacity=".35"/><circle cx="628" cy="238" r="16" fill="#fff" fill-opacity=".45"/>'
    for i in range(4):
        s += f'<rect x="{470 + i * 40}" y="203" width="30" height="8" rx="4" fill="#071022" fill-opacity=".35"/>'
    s += arrow(672, 200, 736, 200, dashed=False)
    s += box(742, 150, 140, 100, "Callback verified", size=15)
    s += arrow(892, 200, 956, 200, dashed=False)
    s += '<rect x="962" y="105" width="160" height="190" rx="14" fill="#fff" fill-opacity=".06" stroke="#94A3D6" stroke-opacity=".25"/>'
    for i in range(4):
        s += f'<rect x="982" y="{130 + i * 22}" width="{[110, 90, 100, 70][i]}" height="7" rx="3.5" fill="#fff" fill-opacity="{.4 if i == 0 else .2}"/>'
    s += '<rect x="982" y="232" width="70" height="26" rx="13" fill="#34D399" fill-opacity=".25" stroke="#34D399" stroke-opacity=".7"/>'
    s += text(1017, 250, "PAID", size=13, fill="#8CF0BF", weight=700)
    s += '<circle cx="1090" cy="245" r="14" fill="#34D399"/><path d="M1083 245 l5 5 l10 -11" fill="none" stroke="#071022" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    return s


def cylinder(cx, ty, label):
    rx, ry, h = 72, 18, 120
    body = f"M{cx - rx},{ty} L{cx - rx},{ty + h} A{rx},{ry} 0 0 0 {cx + rx},{ty + h} L{cx + rx},{ty}"
    s = f'<path d="{body} Z" fill="#fff" fill-opacity=".07" stroke="#94A3D6" stroke-opacity=".3"/>'
    s += f'<ellipse cx="{cx}" cy="{ty}" rx="{rx}" ry="{ry}" fill="url(#g)" fill-opacity=".55" stroke="#94A3D6" stroke-opacity=".35"/>'
    for k in (1, 2):
        s += f'<path d="M{cx - rx},{ty + k * 38} A{rx},{ry} 0 0 0 {cx + rx},{ty + k * 38}" fill="none" stroke="#94A3D6" stroke-opacity=".25"/>'
    s += text(cx, ty + h + 46, label, size=20, fill="#DCE3FA", weight=700)
    return s


def migration(spec):
    s = cylinder(540, 120, spec["left"]) + cylinder(1040, 120, spec["right"])
    s += arrow(640, 200, 940, 200, dashed=False)
    for i in range(5):
        s += f'<rect x="{666 + i * 54}" y="180" width="30" height="12" rx="6" fill="url(#g)" fill-opacity="{.35 + i * .13}"/>'
    s += '<rect x="640" y="222" width="300" height="10" rx="5" fill="#fff" fill-opacity=".08"/><rect x="640" y="222" width="300" height="10" rx="5" fill="url(#g)"/>'
    return s


def bom(spec):
    s = box(450, 170, 150, 60, spec["root"], grad=True, size=16)
    ys = [90, 175, 260]
    for i, label in enumerate(spec["children"]):
        cy = ys[i] + 25
        s += f'<path d="M600,200 C650,200 660,{cy} 710,{cy}" fill="none" stroke="url(#g)" stroke-width="2.5"/>'
        s += box(710, ys[i], 170, 50, label, size=15)
        s += arrow(882, cy, 950, cy, dashed=False)
        s += box(956, ys[i] + 7, 150, 36, spec["leaves"][i], size=14)
    return s


def phone(x, y, a):
    s = f'<rect x="{x}" y="{y}" width="130" height="250" rx="22" fill="#0A0F20" fill-opacity=".95" stroke="#94A3D6" stroke-opacity=".4" stroke-width="2"/>'
    s += f'<rect x="{x + 45}" y="{y + 9}" width="40" height="6" rx="3" fill="#fff" fill-opacity=".2"/>'
    s += f'<rect x="{x + 14}" y="{y + 30}" width="102" height="34" rx="8" fill="url(#g)" fill-opacity=".85"/>'
    for i in range(3):
        s += f'<rect x="{x + 14}" y="{y + 76 + i * 44}" width="102" height="36" rx="8" fill="#fff" fill-opacity=".06" stroke="#94A3D6" stroke-opacity=".15"/>'
        s += f'<circle cx="{x + 32}" cy="{y + 94 + i * 44}" r="9" fill="url(#g)" fill-opacity=".7"/>'
        s += f'<rect x="{x + 48}" y="{y + 88 + i * 44}" width="{56 - i * 8}" height="6" rx="3" fill="#fff" fill-opacity=".35"/>'
    s += f'<rect x="{x + 14}" y="{y + 212}" width="102" height="22" rx="11" fill="url(#g)"/>'
    return s


def mobile(spec):
    s = phone(470, 75, None) + phone(630, 75, None)
    s += arrow(780, 200, 940, 200, both=True)
    s += box(950, 150, 170, 100, spec["target"], grad=True, size=22)
    return s


def report(spec):
    s = window(430, 50, 720, 300)
    s += '<rect x="452" y="100" width="360" height="30" rx="8" fill="url(#g)" fill-opacity=".85"/>'
    for i in range(6):
        y = 142 + i * 32
        s += f'<rect x="452" y="{y}" width="360" height="26" rx="6" fill="#fff" fill-opacity="{.06 if i % 2 == 0 else .03}"/>'
        s += f'<rect x="466" y="{y + 10}" width="{70 + (i * 23) % 60}" height="6" rx="3" fill="#fff" fill-opacity=".35"/>'
        s += f'<rect x="700" y="{y + 10}" width="{50 + (i * 17) % 40}" height="6" rx="3" fill="#fff" fill-opacity=".22"/>'
    heights = [70, 110, 90, 140, 100, 160]
    for i, hh in enumerate(heights):
        x = 850 + i * 48
        s += f'<rect x="{x}" y="{334 - hh}" width="32" height="{hh}" rx="6" fill="url(#g)" fill-opacity=".85"/>'
    s += '<line x1="840" y1="334" x2="1130" y2="334" stroke="#94A3D6" stroke-opacity=".25"/>'
    return s


DRAW = dict(dashboard=dashboard, portal=portal, flow=flow, chain=chain, payment=payment,
            migration=migration, bom=bom, mobile=mobile, report=report)


def build_svg(proj, spec):
    kind = spec["kind"]
    a1, a2 = ACCENTS[kind]
    b1, b2 = BG.get(proj.get("category", "odoo"), BG["odoo"])
    metric = str(proj.get("metric") or proj["title"])
    label = str(proj.get("metric_label") or "")
    version = str(proj.get("odoo_version") or proj.get("category", "")).upper()

    size = min(80, int(300 / (max(len(metric), 1) * 0.62)))
    chip_w = int(len(version) * 9.2 + 28)

    left = (
        f'<rect x="48" y="56" width="{chip_w}" height="30" rx="15" fill="#fff" fill-opacity=".09" stroke="#fff" stroke-opacity=".18"/>'
        f'<text x="{48 + chip_w / 2}" y="76" font-size="12.5" font-weight="700" fill="#D5DCFF" text-anchor="middle" letter-spacing="1">{esc(version)}</text>'
        f'<text x="48" y="{230}" font-size="{size}" font-weight="800" fill="url(#g)" letter-spacing="-2">{esc(metric)}</text>'
        f'<text x="48" y="266" font-size="21" fill="#AEB9D6">{esc(label)}</text>'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(proj["title"])} illustration" font-family="{FONT}" color="{a2}">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{b1}"/><stop offset="1" stop-color="{b2}"/></linearGradient>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a1}"/><stop offset="1" stop-color="{a2}"/></linearGradient>
<radialGradient id="glow1"><stop offset="0" stop-color="{a1}" stop-opacity=".5"/><stop offset="1" stop-color="{a1}" stop-opacity="0"/></radialGradient>
<radialGradient id="glow2"><stop offset="0" stop-color="{a2}" stop-opacity=".3"/><stop offset="1" stop-color="{a2}" stop-opacity="0"/></radialGradient>
<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#fff" fill-opacity=".08"/></pattern>
<marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{a2}"/></marker>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<rect width="{W}" height="{H}" fill="url(#dots)"/>
<circle cx="1120" cy="-20" r="300" fill="url(#glow1)"/>
<circle cx="120" cy="430" r="260" fill="url(#glow2)"/>
{left}
{DRAW[kind](spec)}
</svg>
'''


def main():
    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    projects = {p["id"]: p for p in data["projects"]}
    OUT.mkdir(parents=True, exist_ok=True)

    missing = [pid for pid in projects if pid not in SPECS]
    if missing:
        print("No diagram spec for:", ", ".join(missing), "(add it to SPECS)")

    text_yaml = DATA.read_text(encoding="utf-8")
    for pid, spec in SPECS.items():
        proj = projects.get(pid)
        if not proj:
            print("Skipping unknown project id:", pid)
            continue
        (OUT / f"{pid}.svg").write_text(build_svg(proj, spec), encoding="utf-8")
        pat = re.compile(r'(  - id: "%s"\n(?:    .*\n|\n)*?    image: ).*' % re.escape(pid))
        text_yaml, n = pat.subn(lambda m: m.group(1) + f'"assets/images/{pid}.svg"', text_yaml, count=1)
        if not n:
            print("No image: line found for", pid)
    DATA.write_text(text_yaml, encoding="utf-8")
    print(f"Wrote {len(SPECS)} banners to {OUT}")


if __name__ == "__main__":
    main()
