#!/usr/bin/env python3
"""
scripts/ingest_models.py — M@TE model ingestion pipeline
=========================================================
Reads _registry.yml, fetches each model's root-level
ro-crate-metadata.json (or ro-create-metadata.json) from GitHub, normalises the
data into a common schema, then generates:

  models/{slug}.qmd               — detailed model page (tabbed layout)
  models/index.qmd                — model listing page (real cards)
  tags/index.qmd                  — tag cloud browse page
  tags/{tag-slug}.qmd             — one page per unique tag
  creators/index.qmd              — A–Z creator listing
  creators/{creator-slug}.qmd     — one page per unique creator

Run this script from the repository root before `quarto render`:
  python scripts/ingest_models.py

No GitHub token is required — all source repos must be public.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Set, Tuple

import requests

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(REPO_ROOT, "_registry.yml")
MODELS_DIR = os.path.join(REPO_ROOT, "models")
TAGS_DIR = os.path.join(REPO_ROOT, "tags")
CREATORS_DIR = os.path.join(REPO_ROOT, "creators")

PLACEHOLDER_IMG = "https://placehold.co/1200x500/D64000/white?text=M%40TE+Model"
PLACEHOLDER_SETUP_IMG = "https://placehold.co/1200x500/2c8ec7/white?text=Model+Setup"

# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def to_slug(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def creator_slug(full_name: str) -> str:
    return to_slug(full_name)


def tag_slug(tag: str) -> str:
    return to_slug(tag)


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def parse_registry(path: str) -> List[dict]:
    """
    Parse a minimal registry YAML with entries under:
      models:
        - slug: ...
          repo: Owner/repo
    """
    entries: List[dict] = []
    current: Dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- slug:"):
                if current.get("slug") and current.get("repo"):
                    entries.append(current)
                current = {"slug": stripped.split(":", 1)[1].strip()}
            elif stripped.startswith("repo:"):
                if current:
                    current["repo"] = stripped.split(":", 1)[1].strip()
    if current.get("slug") and current.get("repo"):
        entries.append(current)
    return entries


def fetch_raw(url: str) -> Optional[str]:
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.text
    except Exception as exc:
        print(f"  WARNING: fetch failed for {url}: {exc}", file=sys.stderr)
    return None


def fetch_ro_crate(repo: str) -> dict:
    """
    Fetch RO-Crate metadata from repository root for a model repository.
    """
    text = None
    source_name = "ro-crate-metadata.json"
    # Keep compatibility with repositories that expose the metadata file
    # using the alternate `ro-create-metadata.json` filename.
    for name in ("ro-crate-metadata.json", "ro-create-metadata.json"):
        url = f"https://raw.githubusercontent.com/{repo}/main/{name}"
        text = fetch_raw(url)
        if text:
            source_name = name
            break
    if not text:
        raise RuntimeError(
            f"Could not fetch ro-crate-metadata.json or ro-create-metadata.json for {repo}"
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {source_name} for {repo}: {exc}") from exc


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _clean(val, default=""):
    if val is None:
        return default
    return str(val).strip()


def always_list(val):
    if val is None or val == "":
        return []
    if isinstance(val, list):
        return val
    return [val]


def resolve(index, ref):
    if isinstance(ref, dict) and ref.get("@id"):
        return index.get(ref["@id"], {})
    return {}


def get_name(node):
    if not isinstance(node, dict):
        return ""
    given = node.get("givenName", "")
    if isinstance(given, list):
        given = given[0] if given else ""
    family = node.get("familyName", "")
    if isinstance(family, list):
        family = family[0] if family else ""
    full = f"{_clean(given)} {_clean(family)}".strip()
    if full:
        return full
    name_val = node.get("name")
    if isinstance(name_val, list):
        return _clean(name_val[0]) if name_val else ""
    return _clean(name_val)


def _strip_doi_prefix(value: str) -> str:
    val = _clean(value)
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "http://dx.doi.org/",
        "doi:",
    )
    for p in prefixes:
        if val.lower().startswith(p):
            return val[len(p):]
    return val


def _is_doi_like(value: str) -> bool:
    low = _clean(value).lower()
    return low.startswith("10.") or low.startswith("doi:") or low.startswith((
        "https://doi.org/",
        "http://doi.org/",
        "http://dx.doi.org/",
    ))


def _first_url(node: dict) -> str:
    for u in always_list(node.get("url")):
        if isinstance(u, dict):
            v = _clean(u.get("@id"))
        else:
            v = _clean(u)
        if v:
            return v
    return ""


def _first_identifier(node: dict, exclude: Optional[Set[str]] = None) -> str:
    exclude = exclude or set()
    for ident in always_list(node.get("identifier")):
        if isinstance(ident, dict):
            val = _clean(ident.get("@id"))
        else:
            val = _clean(ident)
        if not val:
            continue
        norm = _strip_doi_prefix(val).lower()
        if norm in exclude:
            continue
        return _strip_doi_prefix(val) if _is_doi_like(val) else val
    return ""


def discover_graphics(repo: str) -> dict:
    """
    Discover model graphics (.website_material/graphics/) via three strategies:

      1. Scrape GitHub web directory listing
         (https://github.com/{repo}/tree/main/.website_material/graphics).
         Parse <a href> links for image/video files.  This is the primary
         strategy because the web UI has no rate limit for public repos and
         works regardless of filename convention (UUIDs, dashes, etc.).

      2. GitHub REST API
         (https://api.github.com/repos/{repo}/contents/...) — no auth,
         but unauthenticated requests are rate-limited to ~60/hr.  Used as
         a fallback when the web scrape returns no files.

      3. Probe known filenames on raw.githubusercontent.com
         A hardcoded list of common names (fig1.png, Model_evolution.pdf,
         animation.mp4, etc.) is tried directly.  This catches repos where
         the graphics directory exists but the web scrape or API somehow
         failed to enumerate it.

    Classification rules:
      - .gif and .mp4 files                → animation
      - .png, .jpg, .jpeg, .pdf files      → still image
      - first still  → landing_image_url
      - second still → model_setup_image_url
      - animation    → animation_url

    TODO (long-term): Replace auto-discovery with explicit ImageObject
    nodes in the RO-Crate @graph under .website_material.  Each graphic
    would be registered as:
      { "@id": ".website_material/graphics/filename.ext",
        "@type": "ImageObject",
        "encodingFormat": "image/gif",
        "name": "landing_image",          # or "model_setup", "animation"
        "description": "caption text" }
    This would make the crate fully self-describing and eliminate all
    heuristic discovery.
    """
    raw_base = f"https://raw.githubusercontent.com/{repo}/main/.website_material/graphics"

    result = {
        "landing_image_url": "",
        "landing_image_caption": "",
        "model_setup_image_url": "",
        "model_setup_image_caption": "",
        "animation_url": "",
        "animation_caption": "",
    }

    def _classify_assign(files: list) -> bool:
        """Sort filenames into stills/animation and fill result dict.
        Returns True if at least one file was assigned."""
        anim_ext = (".gif", ".mp4")
        still_ext = (".png", ".jpg", ".jpeg", ".pdf")
        anims = [f for f in files if f.lower().endswith(anim_ext)]
        stills = [f for f in files if f.lower().endswith(still_ext)]
        if not anims and not stills:
            return False
        if anims:
            result["animation_url"] = f"{raw_base}/{anims[0]}"
        if stills:
            result["landing_image_url"] = f"{raw_base}/{stills[0]}"
        if len(stills) > 1:
            result["model_setup_image_url"] = f"{raw_base}/{stills[1]}"
        return True

    # --- Strategy 1: scrape GitHub web directory listing ---
    try:
        web_url = f"https://github.com/{repo}/tree/main/.website_material/graphics"
        r = requests.get(web_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            files = list(dict.fromkeys(
                re.findall(
                    r'/blob/main/\.website_material/graphics/([^"\'<>]+\.(?:png|jpg|jpeg|gif|mp4|pdf))',
                    r.text,
                    re.I,
                )
            ))
            if _classify_assign(files):
                return result
    except Exception:
        pass

    # --- Strategy 2: GitHub REST API ---
    try:
        api_url = f"https://api.github.com/repos/{repo}/contents/.website_material/graphics"
        r = requests.get(api_url, timeout=15, headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 200:
            files = [f["name"] for f in r.json() if isinstance(f, dict)]
            if _classify_assign(files):
                return result
    except Exception:
        pass

    # --- Strategy 3: probe known filenames directly ---
    anim_candidates = ["animation.mp4", "animation.gif", "GeolMov.gif"]
    still_candidates = [
        "fig1.png", "figure_2.png", "figure2.png",
        "figure_1.png", "figure1.png", "fig.png",
        "gmd-15-8749-2022-f09.png", "gmd-15-8749-2022-f01-web.png",
        "Model_evolution.pdf", "Model_setup.pdf",
    ]
    for name in anim_candidates + still_candidates:
        candidate = f"{raw_base}/{name}"
        try:
            rr = requests.get(candidate, timeout=15)
            if rr.status_code != 200:
                continue
            ext = name.lower().rsplit(".", 1)[-1]
            if ext in ("gif", "mp4") and not result["animation_url"]:
                result["animation_url"] = candidate
            elif ext in ("png", "jpg", "jpeg", "pdf"):
                if not result["landing_image_url"]:
                    result["landing_image_url"] = candidate
                elif not result["model_setup_image_url"]:
                    result["model_setup_image_url"] = candidate
        except Exception:
            continue

    return result


def _convert_pdf_to_png(url: str, slug: str, label: str) -> str:
    """Convert a PDF graphic URL to a local PNG.

    Downloads the PDF from *url*, converts the first page to PNG using
    pdftoppm, and saves to models/_graphics/{slug}_{label}.png.

    If the URL does not end with ``.pdf``, or if anything fails
    (download error, missing pdftoppm, conversion error), the original
    URL is returned unchanged so the caller's ``onerror`` placeholder
    fallback still works in the HTML.
    """
    if not url.lower().endswith(".pdf"):
        return url

    out_dir = "models/_graphics"
    out_path = os.path.join(out_dir, f"{slug}_{label}.png")
    if os.path.exists(out_path):
        return out_path

    os.makedirs(out_dir, exist_ok=True)

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
            pdf_tmp = f.name

        prefix = os.path.splitext(out_path)[0]
        subprocess.run(
            ["pdftoppm", "-png", "-r", "150", pdf_tmp, prefix],
            check=True,
            capture_output=True,
            timeout=60,
        )
        # pdftoppm creates {prefix}-1.png for the first page
        page1 = f"{prefix}-1.png"
        if os.path.exists(page1) and not os.path.exists(out_path):
            os.rename(page1, out_path)
    except Exception:
        return url
    finally:
        if os.path.exists(pdf_tmp):
            os.unlink(pdf_tmp)

    return out_path if os.path.exists(out_path) else url


def normalise_ro_crate(crate: dict, slug: str, repo: str) -> dict:
    """
    Parse a RO-Crate 1.1 @graph into the common normalised schema dict.
    crate: parsed JSON (has "@graph" key)
    slug: from registry
    repo: "Owner/repo-name"
    Returns the same schema dict as the old normalisers.
    """
    graph = always_list(crate.get("@graph"))
    index = {n.get("@id"): n for n in graph if isinstance(n, dict) and n.get("@id")}
    root = index.get("./", {})

    title = _clean(root.get("name"))
    out_slug = _clean(root.get("alternateName")) or slug
    abstract = _clean(root.get("abstract"))
    description = _clean(root.get("description"))

    identifiers = []
    for ident in always_list(root.get("identifier")):
        if isinstance(ident, dict):
            val = _clean(ident.get("@id"))
        else:
            val = _clean(ident)
        if val:
            identifiers.append(val)
    doi = _strip_doi_prefix(identifiers[0]) if identifiers else ""
    dataset_doi_norm = doi.lower()

    creators = []
    for cref in always_list(root.get("creator")):
        cnode = resolve(index, cref)
        if not cnode and isinstance(cref, dict):
            cnode = cref
        full_name = get_name(cnode)
        if not full_name:
            continue
        orcid = ""
        if isinstance(cref, dict):
            orcid = _clean(cref.get("@id"))
        orcid = orcid.replace("https://orcid.org/", "").replace("http://orcid.org/", "")
        creators.append({"full_name": full_name, "orcid": orcid})

    tags = []
    for kw in always_list(root.get("keywords")):
        if isinstance(kw, dict):
            val = _clean(kw.get("name")) or _clean(kw.get("@id"))
        else:
            val = _clean(kw)
        if val:
            tags.append(val)
    if not tags:
        lower_text = f"{title} {abstract} {description}".lower()
        if "crustal root" in lower_text:
            tags.append("crustal roots")
        if "stability" in lower_text or "stable" in lower_text:
            tags.append("stability")
        if "retrogression" in lower_text:
            tags.append("retrogression")

    citation_ref = always_list(root.get("citation"))
    citation_node = resolve(index, citation_ref[0]) if citation_ref else {}
    pub_authors = []
    for aref in always_list(citation_node.get("author")):
        author_node = resolve(index, aref)
        if not author_node and isinstance(aref, dict):
            author_node = aref
        name = get_name(author_node)
        if name:
            pub_authors.append({"full_name": name})

    publication = {
        "title": _clean(citation_node.get("name")),
        "doi": _strip_doi_prefix(_clean(citation_node.get("@id"))),
        "journal": "",
        "date": _clean(citation_node.get("datePublished")),
        "authors": pub_authors,
    }

    license_ref = root.get("license")
    if isinstance(license_ref, dict):
        licence_url = _clean(license_ref.get("@id")) or _clean(license_ref.get("url"))
        licence_node = resolve(index, license_ref)
    else:
        licence_url = _clean(license_ref)
        licence_node = index.get(licence_url, {})
    licence_name = _clean(licence_node.get("name"))

    creation_ref = root.get("#datasetCreation") or root.get("datasetCreation") or {"@id": "#datasetCreation"}
    creation_node = resolve(index, creation_ref) or index.get("#datasetCreation", {})
    instrument_ref = creation_node.get("instrument")
    instrument_node = resolve(index, instrument_ref)
    if not instrument_node and isinstance(instrument_ref, str):
        instrument_node = index.get(instrument_ref, {})

    sw_name = _clean(instrument_node.get("name"))
    sw_url = _clean(instrument_node.get("url"))
    sw_id = _clean(instrument_node.get("@id"))
    sw_doi = ""
    if _is_doi_like(sw_id):
        sw_doi = _strip_doi_prefix(sw_id)
    else:
        match = re.search(r"zenodo\.org/records?/(\d+)", sw_id)
        if match:
            sw_doi = f"10.5281/zenodo.{match.group(1)}"
    if not sw_doi and sw_url:
        match = re.search(r"zenodo\.org/records?/(\d+)", sw_url)
        if match:
            sw_doi = f"10.5281/zenodo.{match.group(1)}"

    def find_data_node(candidates: List[str]) -> dict:
        for cand in candidates:
            if cand in index:
                return index[cand]
        for node in index.values():
            node_name = _clean(node.get("name"))
            if node_name in candidates:
                return node
        return {}

    model_files_node = find_data_node(["model_code_inputs", "model_inputs"])
    dataset_node = find_data_node(["model_output_data", "model_outputs"])

    model_files_nci_url = _first_url(model_files_node)
    dataset_nci_url = _first_url(dataset_node)

    model_files_existing_id = _first_identifier(model_files_node, exclude={dataset_doi_norm})
    dataset_existing_id = _first_identifier(dataset_node)

    credit_text_vals = always_list(root.get("creditText"))
    credit_text = _clean(credit_text_vals[0]) if credit_text_vals else ""

    funders = []
    for fref in always_list(root.get("funder")):
        fnode = resolve(index, fref)
        if not fnode and isinstance(fref, dict):
            fnode = fref
        fname = _clean(fnode.get("name"))
        if fname:
            funders.append({"name": fname})

    graphics = discover_graphics(repo)

    return {
        "slug": out_slug,
        "title": title,
        "abstract": abstract,
        "description": description,
        "doi": doi,
        "creators": creators,
        "tags": tags,
        "research_tags": tags,
        "compute_tags": [],
        "publication": publication,
        "software": {"name": sw_name, "doi": sw_doi, "url": sw_url},
        "landing_image_url": graphics["landing_image_url"],
        "landing_image_caption": graphics["landing_image_caption"],
        "model_setup_image_url": graphics["model_setup_image_url"],
        "model_setup_image_caption": graphics["model_setup_image_caption"],
        "animation_url": graphics["animation_url"],
        "animation_caption": graphics["animation_caption"],
        "licence_url": licence_url,
        "licence_name": licence_name,
        "dataset_nci_url": dataset_nci_url,
        "dataset_existing_id": dataset_existing_id,
        "dataset_notes": _clean(dataset_node.get("description")),
        "model_files_nci_url": model_files_nci_url,
        "model_files_existing_id": model_files_existing_id,
        "model_files_notes": _clean(model_files_node.get("description")),
        "credit_text": credit_text,
        "funders": funders,
        "source_repo": repo,
    }


# ---------------------------------------------------------------------------
# HTML generation helpers
# ---------------------------------------------------------------------------

def doi_badge(doi: str, href: str = "") -> str:
    if not doi:
        return ""
    if not href:
        href = f"https://doi.org/{doi}" if not doi.startswith("http") else doi
        doi_display = doi.replace("https://doi.org/", "")
    else:
        doi_display = doi.replace("https://doi.org/", "")
    return (
        f'<a class="badge-doi" href="{href}" onclick="event.stopPropagation()" target="_blank" rel="noopener">'
        f'<span class="badge-doi-left">DOI</span>'
        f'<span class="badge-doi-right">{doi_display}</span>'
        f"</a>"
    )


def creator_badges_html(creators: list, linked: bool = True, indent: int = 4) -> str:
    pad = " " * indent
    parts = []
    for c in creators:
        name = c["full_name"]
        if not name:
            continue
        slug = creator_slug(name)
        if linked:
            parts.append(
                f'{pad}<a class="badge-creator" href="/creators/{slug}.html">{name}</a>'
            )
        else:
            parts.append(f'{pad}<span class="badge-creator">{name}</span>')
    return "\n".join(parts)


def tag_badges_html(tags: list, linked: bool = True, indent: int = 4) -> str:
    pad = " " * indent
    parts = []
    for t in tags:
        if not t:
            continue
        slug = tag_slug(t)
        if linked:
            parts.append(
                f'{pad}<a class="badge-tag" href="/tags/{slug}.html">{t}</a>'
            )
        else:
            parts.append(f'{pad}<span class="badge-tag">{t}</span>')
    return "\n".join(parts)


def yaml_esc(val: str) -> str:
    """Escape a string for use in a YAML double-quoted scalar."""
    return val.replace("\\", "\\\\").replace('"', '\\"')


def safe_doi(doi: str) -> str:
    """Return a DOI URL (add https://doi.org/ prefix if needed)."""
    if not doi:
        return ""
    if doi.startswith("http"):
        return doi
    return f"https://doi.org/{doi}"


# ---------------------------------------------------------------------------
# Model .qmd page generator
# ---------------------------------------------------------------------------

TAB_JS = """\
<script>
function switchTab(btn, id) {
  var container = btn.closest('.tab-container');
  container.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  container.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
  btn.classList.add('active');
  container.querySelector('#tab-' + id).classList.add('active');
}
</script>"""


def model_qmd(m: dict) -> str:
    slug = m["slug"]
    title = m["title"]

    # DOI handling
    doi_raw = m["doi"]
    doi_href = safe_doi(doi_raw)
    doi_display = doi_raw.replace("https://doi.org/", "") if doi_raw else ""

    pub = m["publication"]
    pub_doi_href = safe_doi(pub["doi"])

    sw = m["software"]
    sw_doi_href = safe_doi(sw["doi"])

    # Creators for header
    creator_list = m["creators"]
    creator_hdg_badges = creator_badges_html(creator_list, linked=True, indent=4)

    # Research tags
    rtags_html = tag_badges_html(m["research_tags"], linked=True, indent=12)
    # Compute tags
    ctags_html = tag_badges_html(m["compute_tags"], linked=True, indent=12)

    # Model setup image
    ms_url = _convert_pdf_to_png(m["model_setup_image_url"], slug, "setup") or PLACEHOLDER_SETUP_IMG
    ms_cap = m["model_setup_image_caption"] or ""

    # Build snapshot media block
    if m.get("animation_url"):
        anim_url = m["animation_url"]
        anim_cap = m.get("animation_caption", "")
        if anim_url.lower().endswith(".mp4"):
            media_html = f"""      <div class="animation-container">
        <video controls autoplay loop muted playsinline style="max-width:100%; border-radius:6px;">
          <source src="{anim_url}" type="video/mp4" />
          Your browser does not support video playback.
        </video>
      </div>"""
        else:
            media_html = f"""      <div class="animation-container">
        <img src="{anim_url}"
             alt="{anim_cap or 'Model animation'}"
             style="max-width:100%; border-radius:6px;"
             onerror="this.style.display='none'" />
      </div>"""
        if anim_cap:
            media_html += f'\n      <p style="font-size:13px;color:#777;text-align:center;margin-top:0.25rem;">{anim_cap}</p>'
    else:
        li_url = _convert_pdf_to_png(m["landing_image_url"], slug, "landing") or PLACEHOLDER_IMG
        li_cap = m["landing_image_caption"] or ""
        media_html = f"""      <div class="full-width-image">
        <img src="{li_url}"
             alt="{li_cap}"
             style="width:100%; border-radius:6px;"
             onerror="this.src='{PLACEHOLDER_IMG}';" />
      </div>"""
        if li_cap:
            media_html += f'\n      <p style="font-size:13px;color:#777;text-align:center;margin-top:0.25rem;">{li_cap}</p>'

    # Pub authors
    if pub["authors"]:
        pub_authors_str = ", ".join(a["full_name"] for a in pub["authors"] if a["full_name"])
    else:
        pub_authors_str = ""

    # Dataset / code
    ds_nci = m["dataset_nci_url"]
    ds_id = m["dataset_existing_id"]
    ds_notes = m["dataset_notes"]
    mf_nci = m["model_files_nci_url"]
    mf_id = m["model_files_existing_id"]
    mf_notes = m["model_files_notes"]

    # Licence
    lic_url = m["licence_url"]
    lic_name = m["licence_name"] or lic_url

    # Funders
    funder_items = "".join(
        f"    <li>{f['name']}</li>\n" for f in m["funders"] if f["name"]
    )
    funders_block = (
        "<ul>\n" + funder_items + "  </ul>" if funder_items else "<p>Not specified.</p>"
    )

    credit = m["credit_text"]
    source_repo = m["source_repo"]
    source_repo_url = f"https://github.com/{source_repo}"

    # Build data section
    data_tab_parts = []
    if ds_nci:
        data_tab_parts.append(
            f'        <p><strong>Dataset (NCI catalogue):</strong><br/>'
            f'<a href="{ds_nci}" target="_blank" rel="noopener">{ds_nci}</a></p>'
        )
    if ds_id:
        ds_id_url = safe_doi(ds_id) if not ds_id.startswith("http") else ds_id
        data_tab_parts.append(
            f'        <p><strong>Dataset existing identifier:</strong><br/>'
            f'<a href="{ds_id_url}" target="_blank" rel="noopener">{ds_id}</a></p>'
        )
    if ds_notes:
        data_tab_parts.append(f"        <p><strong>Dataset notes:</strong> {ds_notes}</p>")
    if mf_nci:
        data_tab_parts.append(
            f'        <p><strong>Model files (NCI catalogue):</strong><br/>'
            f'<a href="{mf_nci}" target="_blank" rel="noopener">{mf_nci}</a></p>'
        )
    if mf_id:
        mf_id_url = safe_doi(mf_id) if not mf_id.startswith("http") else mf_id
        data_tab_parts.append(
            f'        <p><strong>Model files existing identifier:</strong><br/>'
            f'<a href="{mf_id_url}" target="_blank" rel="noopener">{mf_id}</a></p>'
        )
    if mf_notes:
        data_tab_parts.append(f"        <p><strong>Model files notes:</strong> {mf_notes}</p>")
    data_tab_parts.append(
        f'        <p><strong>Source repository:</strong><br/>'
        f'<a href="{source_repo_url}" target="_blank" rel="noopener">{source_repo_url}</a></p>'
    )
    data_tab_html = "\n".join(data_tab_parts) if data_tab_parts else "        <p>Data information not available.</p>"

    # Build pub section
    if pub["title"]:
        pub_section = f"""        <p>
          <strong>{pub["title"]}</strong><br/>
          {pub_authors_str}<br/>
          <em>{pub["journal"]}</em>{(" — " + pub["date"]) if pub["date"] else ""}<br/>
          {doi_badge(pub["doi"], pub_doi_href) if pub["doi"] else ""}
        </p>"""
    else:
        pub_section = "        <p>Publication information not available.</p>"

    # Build software section
    sw_block_parts = []
    if sw["name"]:
        sw_block_parts.append(f"        <p><strong>{sw['name']}</strong></p>")
    if sw["doi"] or sw["url"]:
        links = []
        if sw["doi"]:
            links.append(f'<a href="{sw_doi_href}" target="_blank" rel="noopener">{sw_doi_href}</a>')
        if sw["url"] and sw["url"] != sw_doi_href:
            links.append(f'<a href="{sw["url"]}" target="_blank" rel="noopener">{sw["url"]}</a>')
        sw_block_parts.append("        <p>" + " · ".join(links) + "</p>")
    sw_block = "\n".join(sw_block_parts) if sw_block_parts else "        <p>Software information not available.</p>"

    # DOI badge for header
    if doi_display:
        doi_badge_html = (
            f'    <a class="badge-doi" href="{doi_href}" target="_blank" rel="noopener">'
            f'<span class="badge-doi-left">DOI</span>'
            f'<span class="badge-doi-right">{doi_display}</span></a>'
        )
    else:
        doi_badge_html = ""

    # Abstract
    abstract = m["abstract"]
    description = m["description"]

    return f"""---
# Generated by scripts/ingest_models.py — do not edit directly.
# Re-run the script to regenerate from {source_repo}
title: "{yaml_esc(title)}"
---

```{{=html}}
<div class="model-page">

  <!-- ── Header ─────────────────────────────────────────────────────────── -->
  <h1>{title}</h1>

  <div class="model-meta-block">
    <strong>DOI:</strong>
    {doi_badge_html if doi_badge_html else "<em>Not yet assigned.</em>"}
    <br/><br/>
    <strong>Creators:</strong><br/>
{creator_hdg_badges}
  </div>

  <!-- ── Tabbed content ──────────────────────────────────────────────────── -->
  <div class="tab-container">
    <div class="tab-nav">
      <button class="tab-btn active" onclick="switchTab(this,'snapshot')">Snapshot</button>
      <button class="tab-btn" onclick="switchTab(this,'overview')">Science Overview</button>
      <button class="tab-btn" onclick="switchTab(this,'setup')">Software &amp; Setup</button>
      <button class="tab-btn" onclick="switchTab(this,'data')">Code &amp; Data</button>
      <button class="tab-btn" onclick="switchTab(this,'meta')">Metadata</button>
    </div>

    <!-- Tab 1: Snapshot -->
    <div id="tab-snapshot" class="tab-panel active">
      <p>{description}</p>
{media_html}
    </div>

    <!-- Tab 2: Science Overview -->
    <div id="tab-overview" class="tab-panel">
      <h2>Research Tags</h2>
      <div>
{rtags_html if rtags_html else "        <p><em>None specified.</em></p>"}
      </div>

      <h2>Associated Publication</h2>
{pub_section}

      <h2>Abstract</h2>
      <p>{abstract}</p>
    </div>

    <!-- Tab 3: Software & Setup -->
    <div id="tab-setup" class="tab-panel">
      <h2>Compute Tags</h2>
      <div>
{ctags_html if ctags_html else "        <p><em>None specified.</em></p>"}
      </div>

      <h2>Software</h2>
{sw_block}

      <h2>Model Setup</h2>
      <div class="full-width-image">
        <img src="{ms_url}"
             alt="{ms_cap}"
             style="width:100%; border-radius:6px;"
             onerror="this.src='{PLACEHOLDER_SETUP_IMG}';" />
      </div>
      {f'<p style="font-size:13px; color:#777; text-align:center; margin-top:0.25rem;">{ms_cap}</p>' if ms_cap else ""}
    </div>

    <!-- Tab 4: Code & Data -->
    <div id="tab-data" class="tab-panel">
{data_tab_html}
    </div>

    <!-- Tab 5: Metadata -->
    <div id="tab-meta" class="tab-panel">
      <h2>Citation</h2>
      {f"<blockquote>{credit}</blockquote>" if credit else "<p><em>See source repository for citation.</em></p>"}

      <h2>Licence</h2>
      <p>
        {f'<a href="{lic_url}" target="_blank" rel="noopener">{lic_name}</a>' if lic_url else (lic_name or "<em>Not specified.</em>")}
      </p>

      <h2>Funders</h2>
      {funders_block}
    </div>
  </div>

</div>

{TAB_JS}
```
"""


# ---------------------------------------------------------------------------
# models/index.qmd generator
# ---------------------------------------------------------------------------

def model_card_html(m: dict) -> str:
    slug = m["slug"]
    title = m["title"]
    title_lc = title.lower()
    tags_lc = " ".join(tag_slug(t) for t in m["tags"])
    creators_lc = " ".join(c["full_name"].lower() for c in m["creators"])

    abstract = m["abstract"]
    if len(abstract) > 300:
        abstract = abstract[:297] + "..."

    img_url = _convert_pdf_to_png(m["landing_image_url"], slug, "card") or PLACEHOLDER_IMG
    doi_raw = m["doi"]
    doi_href = safe_doi(doi_raw)
    doi_display = doi_raw.replace("https://doi.org/", "") if doi_raw else ""

    creator_badges = ""
    for c in m["creators"][:3]:
        name = c["full_name"]
        if name:
            cslug = creator_slug(name)
            creator_badges += f'\n      <a class="badge-creator" href="/creators/{cslug}.html">{name}</a>'

    tag_badges = ""
    for t in m["tags"][:5]:
        if t:
            tslug = tag_slug(t)
            tag_badges += f'\n      <a class="badge-tag" href="/tags/{tslug}.html">{t}</a>'

    doi_block = ""
    if doi_display:
        doi_block = f"""
      <br/>
      <a class="badge-doi" href="{doi_href}" onclick="event.stopPropagation()" target="_blank" rel="noopener">
        <span class="badge-doi-left">DOI</span>
        <span class="badge-doi-right">{doi_display}</span>
      </a>"""

    return f"""
  <!-- ── Model card: {slug} ─────────────────────────────────────────────── -->
  <a href="/models/{slug}.html" class="mc-card-container"
     data-title="{title_lc}"
     data-tags="{tags_lc}"
     data-creators="{creators_lc}">
    <img src="{img_url}"
         alt="{title}"
         onerror="this.src='https://placehold.co/600x300/D64000/white?text=M%40TE+Model';" />
    <h3>{title}</h3>
    <p class="mc-card-abstract">{abstract}</p>
    <div class="mc-card-meta">{creator_badges}
      <br/>{tag_badges}{doi_block}
    </div>
  </a>"""


def write_models_index(models: List[dict]) -> None:
    cards_html = ""
    for m in models:
        cards_html += model_card_html(m)

    content = f"""---
title: "Models"
---

```{{=html}}
<div style="padding: 1rem 0;">
  <input
    class="model-search-box"
    id="model-search"
    type="text"
    placeholder="&#x1F50D; Search models by title, creator, or tag&hellip;"
    oninput="filterModels(this.value)"
  />
</div>

<div class="models-grid" id="models-grid">

{cards_html}

</div>

<p id="no-results" style="display:none; color:#888; font-size:16px;">No models matched your search.</p>

<script>
function filterModels(query) {{
  var q = query.toLowerCase().trim();
  var cards = document.querySelectorAll('#models-grid > [data-title]');
  var visible = 0;
  cards.forEach(function(card) {{
    var text = (
      (card.dataset.title || '') + ' ' +
      (card.dataset.tags  || '') + ' ' +
      (card.dataset.creators || '')
    ).toLowerCase();
    var show = !q || text.includes(q);
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  }});
  document.getElementById('no-results').style.display = (visible === 0) ? '' : 'none';
}}
// Support ?q= URL parameter for deep-linking from tag/creator pages
(function() {{
  var params = new URLSearchParams(window.location.search);
  var q = params.get('q');
  if (q) {{
    var box = document.getElementById('model-search');
    if (box) {{ box.value = q; filterModels(q); }}
  }}
}})();
</script>
```
"""
    path = os.path.join(MODELS_DIR, "index.qmd")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {path}")


# ---------------------------------------------------------------------------
# tags/ generators
# ---------------------------------------------------------------------------

def write_tags_index(all_tags: Dict[str, List[dict]], research_tag_set: Set[str], compute_tag_set: Set[str]) -> None:
    """all_tags: {tag_display_string: [model_dict, ...]}"""
    # Sort case-insensitively
    sorted_tags = sorted(all_tags.keys(), key=lambda t: t.lower())

    research = [t for t in sorted_tags if tag_slug(t) in research_tag_set]
    compute = [t for t in sorted_tags if tag_slug(t) in compute_tag_set and tag_slug(t) not in research_tag_set]
    other = [t for t in sorted_tags if tag_slug(t) not in research_tag_set and tag_slug(t) not in compute_tag_set]

    def cloud_items(tags):
        html = ""
        for tag in tags:
            tslug = tag_slug(tag)
            count = len(all_tags[tag])
            html += f'  <a class="badge-tag" href="/tags/{tslug}.html">{tag} <small>({count})</small></a>\n'
        return html

    sections = ""
    if research:
        sections += "<h2>Research Tags</h2>\n<div class=\"tag-cloud\">\n" + cloud_items(research) + "</div>\n\n"
    if compute:
        sections += "<h2>Compute Tags</h2>\n<div class=\"tag-cloud\">\n" + cloud_items(compute) + "</div>\n\n"
    if other:
        sections += "<h2>Other Tags</h2>\n<div class=\"tag-cloud\">\n" + cloud_items(other) + "</div>\n\n"

    content = f"""---
title: "Tags"
---

```{{=html}}
<p>Browse all tags used across M@TE models. Click a tag to see related models.</p>

{sections}
```
"""
    path = os.path.join(TAGS_DIR, "index.qmd")
    os.makedirs(TAGS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {path}")


def write_tag_page(tag: str, models: List[dict]) -> None:
    tslug = tag_slug(tag)
    cards_html = "".join(model_card_html(m) for m in models)
    content = f"""---
title: "Tag: {yaml_esc(tag)}"
---

```{{=html}}
<p>Models tagged with <span class="badge-tag">{tag}</span>:</p>

<div class="models-grid">
{cards_html}
</div>
```
"""
    path = os.path.join(TAGS_DIR, f"{tslug}.qmd")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {path}")


# ---------------------------------------------------------------------------
# creators/ generators
# ---------------------------------------------------------------------------

def write_creators_index(all_creators: Dict[str, List[dict]]) -> None:
    """all_creators: {full_name: [model_slug, ...]}"""
    sorted_names = sorted(all_creators.keys(), key=lambda n: n.split()[-1].lower())

    items_html = ""
    for name in sorted_names:
        cslug = creator_slug(name)
        count = len(all_creators[name])
        items_html += f'  <li><a href="/creators/{cslug}.html">{name}</a> <small>({count} model{"s" if count != 1 else ""})</small></li>\n'

    content = f"""---
title: "Creators"
---

```{{=html}}
<p>All model creators in the M@TE catalogue, listed alphabetically by family name.</p>

<ul class="creator-list">
{items_html}
</ul>
```
"""
    path = os.path.join(CREATORS_DIR, "index.qmd")
    os.makedirs(CREATORS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {path}")


def write_creator_page(name: str, models: List[dict]) -> None:
    cslug = creator_slug(name)
    cards_html = "".join(model_card_html(m) for m in models)
    content = f"""---
title: "{yaml_esc(name)}"
---

```{{=html}}
<p>Models by <span class="badge-creator">{name}</span>:</p>

<div class="models-grid">
{cards_html}
</div>
```
"""
    path = os.path.join(CREATORS_DIR, f"{cslug}.qmd")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Read registry
    entries = parse_registry(REGISTRY_PATH)
    print(f"Found {len(entries)} model(s) in registry.")

    models = []
    for entry in entries:
        slug = entry["slug"]
        repo = entry["repo"]
        print(f"\nIngesting: {slug} from {repo}")
        crate = fetch_ro_crate(repo)
        m = normalise_ro_crate(crate, slug, repo)
        models.append(m)
        print(f"  Format: ro-crate  |  title: {m['title'][:60]}")

    # Write individual model pages
    os.makedirs(MODELS_DIR, exist_ok=True)
    for m in models:
        path = os.path.join(MODELS_DIR, f"{m['slug']}.qmd")
        with open(path, "w", encoding="utf-8") as f:
            f.write(model_qmd(m))
        print(f"  Wrote {path}")

    # Write models/index.qmd
    write_models_index(models)

    # Build tag index — deduplicate by slug so "Python" and "python" merge
    _tag_slug_map: Dict[str, Tuple[str, List[dict]]] = {}  # slug → (display, models)
    for m in models:
        for tag in m["tags"]:
            if tag:
                tslug = tag_slug(tag)
                if tslug not in _tag_slug_map:
                    _tag_slug_map[tslug] = (tag, [])
                _tag_slug_map[tslug][1].append(m)
    all_tags: Dict[str, List[dict]] = {display: ms for _slug, (display, ms) in _tag_slug_map.items()}

    # Track which slugs are research vs compute tags
    research_slug_set: Set[str] = set()
    compute_slug_set: Set[str] = set()
    for m in models:
        for t in m["research_tags"]:
            if t:
                research_slug_set.add(tag_slug(t))
        for t in m["compute_tags"]:
            if t:
                compute_slug_set.add(tag_slug(t))

    # Write tags/
    os.makedirs(TAGS_DIR, exist_ok=True)
    write_tags_index(all_tags, research_slug_set, compute_slug_set)
    for tag, tag_models in all_tags.items():
        write_tag_page(tag, tag_models)

    # Build creator index
    all_creators: Dict[str, List[dict]] = {}
    for m in models:
        for c in m["creators"]:
            name = c["full_name"]
            if name:
                all_creators.setdefault(name, []).append(m)

    # Write creators/
    os.makedirs(CREATORS_DIR, exist_ok=True)
    write_creators_index(all_creators)
    for name, creator_models in all_creators.items():
        write_creator_page(name, creator_models)

    print("\nDone. Commit the generated .qmd files and run `quarto render`.")


if __name__ == "__main__":
    main()
