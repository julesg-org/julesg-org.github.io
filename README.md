# julesg-org.github.io — M@TE Quarto Replica (`jmate-multi` branch)

[![Publish Quarto Site (jmate)](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml/badge.svg)](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml)

A **Quarto-based static website** that replicates the design and structure of the
[M@TE (Model Atlas of the Earth)](https://mate.science/) website, with a
**data-driven model ingestion pipeline** that pulls content directly from model
repositories on GitHub.

> **Branch:** `jmate-multi` (based on `jmate`) — adds the multi-model ingestion pipeline.

Original M@TE site: <https://mate.science/>  
Original M@TE source: <https://github.com/ModelAtlasofTheEarth/website>

---

## 🗂️ Repository Structure

```
julesg-org.github.io/           (jmate-multi branch)
├── _quarto.yml                 # ← M@TE site config (navbar, theme, footer)
├── _registry.yml               # ← MODEL REGISTRY: add a model slug+repo here
├── scripts/
│   └── ingest_models.py        # ← Ingest pipeline (run locally before render)
├── index.qmd                   # ← Hero landing page
├── about.qmd                   # ← About M@TE page
├── contact.qmd                 # ← Contact / model submission info
├── styles/
│   └── mate.css                # ← M@TE visual design (colours, badges, tabs)
├── images/
│   └── atlas-icon.svg          # ← M@TE navbar logo (SVG)
├── models/
│   ├── mather-2022-groundwater.qmd  # ← Hand-written reference model page
│   └── (other pages generated on the fly by pre-render)
├── tags/                       # ← Generated on the fly by pre-render
├── creators/                   # ← Generated on the fly by pre-render
├── news/
│   └── index.qmd               # ← News listing page
└── .github/
    └── workflows/
        └── publish.yml         # ← CI/CD: build & deploy on push to jmate
```

---

## 🔄 Development Workflow

### Adding a new model

1. Add an entry to `_registry.yml`:

```yaml
models:
  - slug: my-new-model
    repo: ModelAtlasofTheEarth/my-new-model
```

2. Commit `_registry.yml` and push — CI fetches the model data from GitHub and
   regenerates all pages automatically.

### Running locally

```bash
# 1. Clone the repo and check out this branch
git clone https://github.com/julesg-org/julesg-org.github.io.git
cd julesg-org.github.io
git checkout julesghub-nodup

# 2. Install Python dependencies (one-time setup)
pip install requests

# 3. Preview or build — the ingest script runs automatically via pre-render
quarto preview
# or
quarto render
```

The `pre-render` hook in `_quarto.yml` runs `python scripts/ingest_models.py`
before every render, so model pages are always up-to-date with their source
repositories on GitHub. Generated `.qmd` files live only on disk during
rendering and are never committed.

---

## 🎨 Design

The M@TE design is replicated from the original Gatsby/Netlify site:

| Element | Value |
|---------|-------|
| Primary colour | `#D64000` (rust/orange-red) |
| Link colour | `#2c8ec7` (blue) |
| Navbar background | `rgba(240, 248, 250, 0.85)` semi-transparent |
| Font | Open Sans Bold, sans-serif |
| Tag badges | Blue (`#2c8ec7`), link to `/tags/{slug}.html` |
| Creator badges | Grey (`#6c757d`), link to `/creators/{slug}.html` |
| DOI badges | Two-part: grey `#555` + blue `#007ec6` |

---

## 📄 Pages

| Page | File | Description |
|------|------|-------------|
| Home | `index.qmd` | Hero section + model card grid + highlights |
| Models | `models/index.qmd` | Searchable/filterable model listing (generated) |
| Model detail | `models/{slug}.qmd` | Full model page with 5-tab layout (generated) |
| Tags | `tags/index.qmd` | Tag cloud browse page (generated) |
| Tag detail | `tags/{tag}.qmd` | Models sharing a tag (generated) |
| Creators | `creators/index.qmd` | A–Z creator listing (generated) |
| Creator detail | `creators/{creator}.qmd` | Models by a creator (generated) |
| News | `news/index.qmd` | News listing placeholder |
| About | `about.qmd` | What M@TE is and how it works |
| Contact | `contact.qmd` | Model submission info |

---

## 🚀 Deployment

Deployment is fully automatic via GitHub Actions:

1. Push to `julesghub-nodup` (or any branch configured for CI)
2. GitHub Actions installs Python, runs `pip install requests`, then runs `quarto render`
3. The `pre-render` hook automatically fetches model metadata from GitHub and generates all pages
4. The `_site/` directory is pushed to the `gh-pages` branch
5. GitHub Pages serves it at **https://julesg-org.github.io**

See **[.github/workflows/publish.yml](.github/workflows/publish.yml)** for the workflow.




