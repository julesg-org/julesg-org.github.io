# images/

This folder holds all images used across the site.

## Files to add here

| Filename | Recommended size | Purpose |
|---|---|---|
| `logo.png` | 80 × 80 px | Navbar logo (referenced in `_quarto.yml`) |
| `favicon.png` | 32 × 32 px | Browser tab icon |
| `profile.png` | 400 × 400 px | Profile photo on the About page |
| `og-card.png` | 1200 × 630 px | Open Graph / Twitter card image |
| `hero.png` | 400 × 400 px | Optional hero illustration on the home page |

## Where images are referenced

- **Logo / favicon** → `_quarto.yml` under `website > navbar > logo` and `website > favicon`
- **Profile photo** → `about.qmd` under `image:`
- **Social card** → `_quarto.yml` under `website > open-graph > image` and `website > twitter-card > image`
- **Post cover images** → individual post `index.qmd` files under `image:`

## Generating placeholder images (quick start)

If you just want something to display while building the site, create simple
coloured PNG files with ImageMagick:

```bash
# Install ImageMagick if needed: sudo apt install imagemagick
magick -size 80x80  xc:#5b6ef5 images/logo.png
magick -size 32x32  xc:#5b6ef5 images/favicon.png
magick -size 400x400 xc:#e0fbf7 images/profile.png
magick -size 1200x630 xc:#eef0ff images/og-card.png
```

Replace these with real images before launching publicly.
