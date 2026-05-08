# julesg-org.github.io — Source Repository

[![Deploy Quarto Site](https://github.com/julesg-org/julesg-org.github.org/actions/workflows/deploy.yml/badge.svg)](https://github.com/julesg-org/julesg-org.github.org/actions/workflows/deploy.yml)

The source repository for **[julesg-org.github.io](https://julesg-org.github.io)** — built with [Quarto](https://quarto.org) and deployed automatically to GitHub Pages.

---

## 🗂️ Repository Structure

```
julesg-org.github.org/
├── _quarto.yml                     # ← Site-wide config (navbar, theme, footer)
├── index.qmd                       # ← Home page
├── about.qmd                       # ← About page
├── styles.css                      # ← Custom CSS overrides
├── images/                         # ← Logos, profile photos, cover images
│   └── README.md                   #   (placeholder instructions)
├── blog/
│   ├── index.qmd                   # ← Blog listing page
│   └── posts/
│       └── welcome/
│           └── index.qmd           # ← Sample "Welcome" blog post
├── projects/
│   ├── index.qmd                   # ← Projects listing page
│   └── sample-project/
│       └── index.qmd               # ← Dummy "other org repo" project page
└── .github/
    └── workflows/
        └── deploy.yml              # ← CI/CD: build & deploy on push to main
```

---

## ✏️ How to Edit the Site

### 1 — Edit global settings

Open **`_quarto.yml`** to change:
- Site title, description, and URL
- Navbar links (add new pages here)
- Theme (Bootswatch: `cosmo`, `flatly`, `litera`, etc.)
- Footer text and social-media links

### 2 — Edit page content

Each `.qmd` file is a page.  Every file contains a YAML front matter block
(between `---` markers) with per-page settings, followed by Markdown content.

| Page | File |
|------|------|
| Home | `index.qmd` |
| About | `about.qmd` |
| Blog listing | `blog/index.qmd` |
| Welcome post | `blog/posts/welcome/index.qmd` |
| Projects listing | `projects/index.qmd` |
| Sample project | `projects/sample-project/index.qmd` |

### 3 — Add a new blog post

```bash
mkdir -p blog/posts/my-new-post
cp blog/posts/welcome/index.qmd blog/posts/my-new-post/index.qmd
# Edit blog/posts/my-new-post/index.qmd — update title, date, content
```

### 4 — Customise styles

Edit **`styles.css`** to tweak colours, fonts, spacing, and card layouts.
The file uses CSS custom properties (design tokens) at the top — change the
hex values there to restyle the whole site instantly.

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

## 🤝 Adding Content from Another Org Repository

Other repositories in the `julesg-org` organisation can contribute pages to
this site.  See **[projects/sample-project/index.qmd](projects/sample-project/index.qmd)**
for a worked example and full instructions.

**Quick summary:**

1. Create `projects/<your-repo-name>/index.qmd` in *this* repo.
2. Fill it with your project's title, description, and content.
3. Open a pull request — the page appears on the site after merge.

For **live sync** with the source repo, add it as a Git submodule:

```bash
git submodule add https://github.com/julesg-org/your-repo projects/your-repo/repo
```

The CI workflow already runs `git submodule update --init --recursive` so
submodule content is fetched automatically on every build.

---

## 📦 Deployment

Deployment is fully automatic:

1. Push to `main`
2. GitHub Actions builds the site with `quarto render`
3. The `_site/` directory is pushed to the `gh-pages` branch
4. GitHub Pages serves it at **https://julesg-org.github.io**

See **[.github/workflows/deploy.yml](.github/workflows/deploy.yml)** for the full workflow and customisation notes.

### One-time GitHub setup

In your repository go to **Settings → Pages** and set:

- **Source:** Deploy from a branch
- **Branch:** `gh-pages` / `root`
