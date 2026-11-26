# Hammad Ali: Odoo portfolio

Live: https://4858hammad.github.io

Static site generated from `portfolio_data.yaml` (profile, experience, projects) and `data/apps.json` (37 NeuralBytea apps).

```bash
pip install pyyaml
python tools/build_site.py      # rebuilds every page, sitemap and worker/src/knowledge.js
```

Edit the YAML, rebuild, commit the generated HTML. GitHub Actions rebuilds on push to `main` and deploys with Jekyll.

## Layout
- `assets/style.css`, `assets/site.js`: design system and page behaviour
- `assets/chat.js`: "Ask AI" widget
- `worker/`: Cloudflare Worker proxy for the chat (see `worker/README.md`)
- `assets/cv_*.html`, `build_ats_cv.py`, `tools/build_visuals.py`: CV sources and project visuals

## Ask AI
Set the repo variable `CHAT_ENDPOINT` to the deployed Worker URL (recommended; the Groq key stays on the Worker). With no endpoint, an Actions secret `GROQ_API_KEY` enables direct mode, where the key is visible in the browser. With neither, the widget is hidden.
