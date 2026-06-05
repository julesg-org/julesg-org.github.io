# julesg-org.github.io — M@TE Quarto Replica (`jmate` branch)

[![Publish Quarto Site (jmate)](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml/badge.svg)](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml)

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

That single command installs all dependencies (Python, Quarto, poppler),
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
├── _quarto.yml                  # ← M@TE site config (navbar, theme, footer)
├── _registry.yml                # ← MODEL REGISTRY: add a model slug+repo here
├── scripts/
│   └── ingest_models.py         # ← Ingest pipeline (fetches metadata + graphics)
├── index.qmd                    # ← Hero landing page
├── about.qmd                    # ← About M@TE page
├── contact.qmd                  # ← Contact / model submission info
├── styles/
│   └── mate.css                 # ← M@TE visual design (colours, badges, tabs)
├── images/
│   ├── atlas-icon.svg           # ← M@TE navbar logo (SVG)
│   └── AuScopeLogo.webp        # ← Funder logo
├── models/
│   ├── _graphics/               # ← Auto-generated PNGs (converted from PDFs)
│   ├── index.qmd                # ← Model listing (generated)
│   └── {slug}.qmd               # ← Per-model detail page (generated)
├── tags/                        # ← Generated tag pages (one per tag)
├── creators/                    # ← Generated creator pages (one per creator)
├── news/
│   └── index.qmd                # ← News listing page
└── .github/
    └── workflows/
        └── publish.yml          # ← CI/CD: pixi run build → deploy to gh-pages
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
| `pixi run preview` | Start a local Quarto preview server |
| `pixi run build` | Ingest + render (no preview) — used in CI |
| `pixi run heymate` | Ingest + render + preview — full local version of m@te website |
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

1. Push to the `jmate` branch
2. GitHub Actions runs `prefix-dev/setup-pixi@v0.9.6` (which installs pixi and
   all dependencies from `pixi.toml` — Python, Quarto, poppler — with caching)
3. `pixi run build` fetches model metadata from GitHub, generates all pages,
   PDF thumbnails, and renders the full site
4. The `_site/` directory is pushed to the `gh-pages` branch
5. GitHub Pages serves it at **https://julesg-org.github.io**

See **[.github/workflows/publish.yml](.github/workflows/publish.yml)** for the workflow.




