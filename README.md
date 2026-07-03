# julesg-org.github.io — M@TE Quarto Replica

[![Publish Quarto Site](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml/badge.svg)](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml)

A **Quarto-based static website** that replicates the design and structure of the
[M@TE (Model Atlas of the Earth)](https://mate.science/) website, with a
**data-driven model ingestion pipeline** that pulls content directly from model
repositories on GitHub.

Original M@TE site: <https://mate.science/>  
Original M@TE source: <https://github.com/ModelAtlasofTheEarth/website>

---

## Quick Start

```bash
git clone https://github.com/julesg-org/julesg-org.github.io.git
cd julesg-org.github.io
pixi run heymate
```

`pixi` installs all dependencies (Python, Quarto, poppler),
fetches model metadata from GitHub, generates all pages, renders the site,
and opens a local preview in your browser.

> **Prerequisite:** [pixi](https://pixi.sh) — a cross-platform package manager.
> Install it on any platform:
> - **Linux / macOS:** `curl -fsSL https://pixi.sh/install.sh | sh`
> - **macOS (Homebrew):** `brew install pixi`
> - **Windows:** `winget install pixi` or `scoop install pixi`
> - **Any (via conda):** `conda install -c conda-forge pixi`

---

## 🗂️ Repository Structure

```
julesg-org.github.io/
├── pixi.toml                    # ← Single dependency manifest (Python, Quarto, poppler)
├── _quarto.yml                  # ← M@TE site config; registers pandoc filter + global JS
├── _registry.yml                # ← MODEL REGISTRY: add a model slug+repo here
├── scripts/
│   ├── __init__.py              # ← Makes scripts/ a package (enables filter imports)
│   ├── ingest_models.py         # ← Ingest pipeline (fetches metadata + graphics)
│   ├── model_renderer.py        # ← Shared HTML generation (model pages + cards)
│   └── model-tabs.js            # ← switchTab() JS, included globally via _quarto.yml
├── _extensions/
│   └── mate/
│       └── model-page.py        # ← Pandoc filter: reads YAML frontmatter → renders HTML
├── index.qmd                    # ← Hero landing page
├── about.qmd                    # ← About M@TE page
├── contact.qmd                  # ← Contact / model submission info
├── styles/
│   └── mate.css                 # ← M@TE visual design (colours, badges, tabs)
├── images/
│   ├── atlas-icon.svg           # ← M@TE navbar logo (SVG)
│   └── AuScopeLogo.webp         # ← Funder logo
├── models/
│   ├── _graphics/               # ← Auto-generated PNGs (converted from PDFs, gitignored)
│   ├── index.qmd                # ← Model listing page (generated, gitignored)
│   └── {slug}.qmd               # ← Per-model YAML frontmatter only (generated, gitignored)
├── tags/                        # ← Generated tag pages (one per tag, gitignored)
├── creators/                    # ← Generated creator pages (one per creator, gitignored)
├── news/
│   └── index.qmd                # ← News listing page
└── .github/
    └── workflows/
        └── publish.yml          # ← CI/CD: pixi run build → gh-pages + Netlify
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

2. Run `pixi run ingest` to fetch model metadata and regenerate all pages locally,
   or just commit and push — CI handles everything automatically.

### Running locally

```bash
# 1. Clone the repo
git clone https://github.com/julesg-org/julesg-org.github.io.git
cd julesg-org.github.io

# 2. Ingest model data, render the site, and open a preview
pixi run heymate
```

**Breakdown of pixi tasks:**

| Command | What it does |
|---------|-------------|
| `pixi run ingest` | Fetch model metadata from GitHub, discover graphics, generate `.qmd` files |
| `pixi run render` | Render the site with Quarto to `_site/` |
| `pixi run preview` | 'render' + start a local Quarto server |
| `pixi run build` | Ingest + render (no preview) — used in CI |
| `pixi run heymate` | Ingest + preview — full local version of m@te website |
| `pixi run clean` | Remove all generated files to force a fresh rebuild |

The ingest must run **before** every render to ensure model pages reflect
the latest metadata. `pixi run build` and `pixi run heymate` handle this ordering
automatically.

All generated files (`.qmd` pages, `_graphics/` PNGs, `_site/`, `_freeze/`,
`.quarto/`) are gitignored — they live only on disk during rendering and are
never committed. Run `pixi run clean` to wipe them all, then `pixi run build`
for a pristine rebuild.

---

## 🎨 Design

The M@TE design is replicated from the original Gatsby/Netlify site:

| Element | Value |
|---------|-------|
| Primary colour | `#D64000` (rust/orange-red) |
| Link colour | `#2c8ec7` (blue) |
| Navbar / hero background | `#DAE1E3` (light grey-blue) |
| Font | Open Sans Bold, sans-serif |
| Tag badges | Blue (`#2c8ec7`), link to `/tags/{slug}.html` |
| Creator badges | Grey (`#6c757d`), link to `/creators/{slug}.html` |
| DOI badges | Two-part: grey `#555` + blue `#007ec6` |

---

## 📄 Pages

| Page | File | Source | Description |
|------|------|--------|-------------|
| Home | `index.qmd` | hand-authored | Hero section + model card grid + highlights |
| Models | `models/index.qmd` | generated | Searchable/filterable model listing |
| Model detail | `models/{slug}.qmd` | generated | YAML frontmatter only — HTML rendered at build time by pandoc filter |
| Tags | `tags/index.qmd` | generated | Tag cloud browse page |
| Tag detail | `tags/{tag}.qmd` | generated | All models sharing a tag |
| Creators | `creators/index.qmd` | generated | A–Z creator listing |
| Creator detail | `creators/{creator}.qmd` | generated | All models by a creator |
| News | `news/index.qmd` | hand-authored | News listing placeholder |
| About | `about.qmd` | hand-authored | What M@TE is and how it works |
| Contact | `contact.qmd` | hand-authored | Model submission info |

### How model detail pages are rendered

The per-model QMDs (`models/{slug}.qmd`) contain **no HTML body** — only a YAML
frontmatter block with all model data nested under a `model:` key:

```yaml
---
title: "My Model Title"
model:
  slug: my-model
  abstract: "..."
  description: "..."
  creators: [...]
  publication: {...}
  # ... all other fields
---
```

At render time, the pandoc filter `_extensions/mate/model-page.py` intercepts
each document, reads the `model:` metadata, calls
`scripts/model_renderer.render_model_page()`, and replaces the empty document
body with the full five-tab HTML layout.  The tab-switching JS
(`scripts/model-tabs.js`) is injected once globally via `_quarto.yml` rather
than being duplicated in each page.

This separation means:
- Model data is **readable and diffable** in the `.qmd` files (plain YAML, ~130 lines each)
- All HTML generation logic lives in **one place** (`scripts/model_renderer.py`)
- Adding or changing the page layout requires editing only `model_renderer.py`, not every generated file

---

## 🚀 Deployment

Deployment is fully automatic via GitHub Actions. A single workflow builds the
site once with pixi and then deploys the output to two independent targets.

See **[.github/workflows/publish.yml](.github/workflows/publish.yml)** for the
full workflow.

### GitHub Pages

1. Push to the `main` branch
2. GitHub Actions runs `prefix-dev/setup-pixi@v0.9.6` (installs pixi and all
   dependencies from `pixi.toml` — Python, Quarto, poppler — with caching)
3. `pixi run build` fetches model metadata from GitHub, generates all pages,
   PDF thumbnails, and renders the full site to `_site/`
4. `peaceiris/actions-gh-pages` pushes `_site/` to the `gh-pages` branch
5. GitHub Pages serves it at **https://julesg-org.github.io**

### Netlify TODO

After the build step, `nwtgck/actions-netlify` deploys the same `_site/`
output directly to Netlify via the Netlify API — GHA does all the building,
Netlify only serves the result.

Site: **https://\<your-netlify-site\>.netlify.app**

#### Required secrets

Add these in **GitHub → repo Settings → Secrets and variables → Actions**:

| Secret | Where to get it |
|--------|----------------|
| `NETLIFY_AUTH_TOKEN` | Netlify UI → User settings → Personal access tokens → New token |
| `NETLIFY_SITE_ID` | Netlify UI → Site → Site configuration → Site ID (a UUID) |


After this, Netlify only receives deployments pushed by GHA — it never triggers
its own build from a Git push.

#### Independence of the two deploy targets

The GitHub Pages step and the Netlify step are independent — neither depends on
the other. Removing or disabling one does not affect the other.
