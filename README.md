# julesg-org.github.io — M@TE Quarto Replica (`jmate` branch)

[![Publish Quarto Site (jmate)](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml/badge.svg)](https://github.com/julesg-org/julesg-org.github.io/actions/workflows/publish.yml)

A **Quarto-based static website** that replicates the design and structure of the
[M@TE (Model Atlas of the Earth)](https://mate.science/) website.

> **Branch:** `jmate` — all M@TE files live here. The `main` branch contains the original organisation site.

Original M@TE site: <https://mate.science/>  
Original M@TE source: <https://github.com/ModelAtlasofTheEarth/website>

---

## 🗂️ Repository Structure

```
julesg-org.github.io/           (jmate branch)
├── _quarto.yml                 # ← M@TE site config (navbar, theme, footer)
├── index.qmd                   # ← Hero landing page with model cards
├── about.qmd                   # ← About M@TE page
├── contact.qmd                 # ← Contact / model submission info
├── styles/
│   └── mate.css                # ← M@TE visual design (colours, badges, cards)
├── images/
│   └── atlas-icon.svg          # ← M@TE navbar logo (SVG)
├── models/
│   ├── index.qmd               # ← Searchable model listing page
│   └── mather-2022-groundwater.qmd  # ← Full model detail page
├── news/
│   └── index.qmd               # ← News listing page
└── .github/
    └── workflows/
        └── publish.yml         # ← CI/CD: build & deploy on push to jmate
```

---

## 🎨 Design

The M@TE design is replicated from the original Gatsby/Netlify site:

| Element | Value |
|---------|-------|
| Primary colour | `#D64000` (rust/orange-red) |
| Link colour | `#2c8ec7` (blue) |
| Navbar background | `rgba(240, 248, 250, 0.85)` semi-transparent |
| Font | Open Sans Bold, sans-serif |
| Tag badges | Blue (`#2c8ec7`) |
| DOI badges | Two-part: grey `#555` + blue `#007ec6` |

---

## 📄 Pages

| Page | File | Description |
|------|------|-------------|
| Home | `index.qmd` | Hero section + model card grid + highlights |
| Models | `models/index.qmd` | Searchable/filterable model listing |
| Model detail | `models/mather-2022-groundwater.qmd` | Full model page (example) |
| News | `news/index.qmd` | News listing placeholder |
| About | `about.qmd` | What M@TE is and how it works |
| Contact | `contact.qmd` | Model submission info |

---

## 🚀 Local Development

### Prerequisites

- [Quarto CLI](https://quarto.org/docs/get-started/) ≥ 1.5

### Commands

```bash
# Preview the site with live reload (opens in browser)
quarto preview

# Build the site (output → _site/)
quarto render
```

---

## 📦 Deployment

Deployment is fully automatic via GitHub Actions:

1. Push to the `jmate` branch
2. GitHub Actions builds the site with `quarto render`
3. The `_site/` directory is pushed to the `gh-pages` branch
4. GitHub Pages serves it at **https://julesg-org.github.io**

> **Note:** The `main` branch deploys the original organisation site via `.github/workflows/deploy.yml`.
> The `jmate` branch deploys the M@TE replica via `.github/workflows/publish.yml`.
> If both branches are active, the last push wins on the shared `gh-pages` branch.
> To deploy both independently, consider using a subdirectory (e.g., `gh-pages:/jmate/`) or a separate GitHub Pages deployment environment.

See **[.github/workflows/publish.yml](.github/workflows/publish.yml)** for the workflow.

### One-time GitHub setup

In your repository go to **Settings → Pages** and set:

- **Source:** Deploy from a branch
- **Branch:** `gh-pages` / `root`

---

## 🔄 M@TE Content Ingestion Mechanism

The original M@TE website uses an automated mechanism to pull model content from individual repositories:

1. Each scientific model has its own GitHub repository in the `ModelAtlasofTheEarth` organisation
2. Each model repo contains a `.website_material/` folder with graphics and an `index.md` with rich YAML metadata
3. When a GitHub issue is labelled `"model published"`, a GitHub Actions workflow fires automatically
4. It copies the `.website_material/` contents into the website repo and opens a pull request
5. After merge, the site rebuilds and the new model appears at mate.science

This Quarto replica can adopt a similar workflow — model repositories could contribute `.qmd` files to the `models/` directory via pull requests.

