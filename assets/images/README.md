# Project images

Two kinds of image, for two jobs.

## 1. Solution diagrams (generated, already done)

`projects/<id>.png` (banner, 1800×600) and `og/<id>.png` (link preview, 1200×630)
show how each system works: the steps, which parts were built in Odoo, which are
external, and the result. Every label comes from `portfolio_data.yaml`, and the
flow for each project is written in `tools/visuals.yaml`.

They are labelled "Solution diagram" on purpose. They are not screenshots, and
the site never calls them screenshots.

To change one, edit `tools/visuals.yaml`, then:

```bash
pip install pyyaml playwright pillow
python -m playwright install chromium     # once
python tools/build_visuals.py <project-id> # or no id for all
python tools/build_pages.py
```

## 2. Real screenshots (you add these, case study by case study)

Add them to a project in `portfolio_data.yaml`, and the case-study page shows a
"Screens" gallery:

```yaml
    screenshots:
      - src: assets/images/screens/tti-attendance-dashboard-1.png
        caption: "Attendance board, demo data"
```

Rules, so a screenshot never leaks a client's data:

- Capture from **your own database with Odoo demo data**, never from a client's
  production system. Install your module (or your NeuralBytea edition of it, once
  the IP question is settled) on a fresh Odoo of the same version.
- No real names, CNICs, salaries, amounts, phone numbers, emails or company logos.
  Demo data ("Mitchell Admin", "Azure Interior") is fine.
- Width 1440 px browser window, 100% zoom, light or dark theme but the same for
  all shots. Save as PNG and run it through https://squoosh.app (target < 300 KB).
- 1–3 shots per featured project. One clear screen beats five busy ones.
