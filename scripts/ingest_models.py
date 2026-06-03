#!/usr/bin/env python3
"""
scripts/ingest_models.py — M@TE model ingestion pipeline
=========================================================
Reads _registry.yml, fetches each model's
.website_material/ro-crate-metadata.json from GitHub, normalises the
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
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
import yaml

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
KNOWN_GRAPHICS: Dict[str, Dict[str, str]] = {
    "ModelAtlasofTheEarth/mather-2022-groundwater": {
        "landing_image_url": "https://raw.githubusercontent.com/ModelAtlasofTheEarth/mather-2022-groundwater/main/.website_material/graphics/fig1.png",
        "model_setup_image_url": "https://raw.githubusercontent.com/ModelAtlasofTheEarth/mather-2022-groundwater/main/.website_material/graphics/figure_2.png",
        "animation_url": "",
    },
    "ModelAtlasofTheEarth/sachau-2022-icesheet": {
        "landing_image_url": "https://raw.githubusercontent.com/ModelAtlasofTheEarth/sachau-2022-icesheet/main/.website_material/graphics/gmd-15-8749-2022-f09.png",
        "model_setup_image_url": "https://raw.githubusercontent.com/ModelAtlasofTheEarth/sachau-2022-icesheet/main/.website_material/graphics/gmd-15-8749-2022-f01-web.png",
        "animation_url": "",
    },
    "ModelAtlasofTheEarth/Yu-2025-granulites": {
        "landing_image_url": "https://github.com/user-attachments/files/23468159/Model_evolution.pdf",
        "model_setup_image_url": "https://github.com/user-attachments/files/23468175/Model_setup.pdf",
        "animation_url": "",
    },
    "ModelAtlasofTheEarth/cenki-tok-2020-crustal-roots-in-stable-continents": {
        "landing_image_url": "https://raw.githubusercontent.com/ModelAtlasofTheEarth/cenki-tok-2020-crustal-roots-in-stable-continents/main/.website_material/graphics/GeolMov.gif",
        "model_setup_image_url": "",
        "animation_url": "https://raw.githubusercontent.com/ModelAtlasofTheEarth/cenki-tok-2020-crustal-roots-in-stable-continents/main/.website_material/graphics/GeolMov.gif",
    },
}

# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def to_slug(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
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

def fetch_raw(url: str) -> Optional[str]:
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.text
    except Exception as exc:
        print(f"  WARNING: fetch failed for {url}: {exc}", file=sys.stderr)
    return None


def fetch_ro_crate(repo: str) -> dict:
    """Fetch and parse the model RO-Crate metadata JSON."""
    url = f"https://raw.githubusercontent.com/{repo}/main/.website_material/ro-crate-metadata.json"
    text = fetch_raw(url)
    if not text:
        raise RuntimeError(f"Could not fetch ro-crate-metadata.json for {repo}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"RO-Crate parse error for {repo}: {exc}") from exc


def fetch_graphics(repo: str) -> Dict[str, str]:
    """
    Discover graphics from .website_material/graphics.
    - landing_image_url: first static image
    - model_setup_image_url: second static image (or landing image if only one)
    - animation_url: first gif/mp4/webm
    """
    api_url = f"https://api.github.com/repos/{repo}/contents/.website_material/graphics"
    out = {"landing_image_url": "", "model_setup_image_url": "", "animation_url": ""}
    try:
        r = requests.get(api_url, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"graphics listing status {r.status_code}")
        items = r.json()
        if not isinstance(items, list):
            raise RuntimeError("graphics listing is not a JSON array")
    except Exception as exc:
        print(f"  WARNING: graphics discovery failed for {repo}: {exc}", file=sys.stderr)
        items = []

    images: List[str] = []
    animations: List[str] = []
    for item in sorted(items, key=lambda i: _clean(i.get("name", "")).lower()):
        if _clean(item.get("type")) != "file":
            continue
        name = _clean(item.get("name", ""))
        url = _clean(item.get("download_url", ""))
        if not url:
            continue
        ext = os.path.splitext(name.lower())[1]
        if ext in {".gif", ".mp4", ".webm"}:
            animations.append(url)
        if ext in {".png", ".jpg", ".jpeg", ".webp"}:
            images.append(url)

    landing = images[0] if images else out["landing_image_url"]
    setup = images[1] if len(images) > 1 else (images[0] if images else out["model_setup_image_url"])
    animation = animations[0] if animations else out["animation_url"]
    out.update(
        {
            "landing_image_url": landing,
            "model_setup_image_url": setup,
            "animation_url": animation,
        }
    )

    known = KNOWN_GRAPHICS.get(repo, {})
    for key in ("landing_image_url", "model_setup_image_url", "animation_url"):
        if not out.get(key):
            out[key] = known.get(key, "")
    if not out["landing_image_url"] and out["animation_url"]:
        out["landing_image_url"] = out["animation_url"]
    if not out["model_setup_image_url"]:
        out["model_setup_image_url"] = out["landing_image_url"]
    return out


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _clean(val, default=""):
    if val is None:
        return default
    return str(val).strip()


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    out = []
    for v in values:
        v = _clean(v)
        if not v:
            continue
        k = v.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(v)
    return out


def _index_graph(crate: dict) -> Dict[str, dict]:
    graph = crate.get("@graph", [])
    if not isinstance(graph, list):
        return {}
    out: Dict[str, dict] = {}
    for node in graph:
        if isinstance(node, dict):
            node_id = _clean(node.get("@id"))
            if node_id:
                out[node_id] = node
    return out


def _resolve_ref(value: Any, nodes: Dict[str, dict]) -> Any:
    if isinstance(value, dict):
        node_id = _clean(value.get("@id"))
        if node_id and node_id in nodes:
            return nodes[node_id]
        return value
    if isinstance(value, str) and value in nodes:
        return nodes[value]
    return value


def _node_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "url", "@id", "description"):
            t = _clean(value.get(key))
            if t:
                return t
        return ""
    if isinstance(value, list):
        for item in value:
            t = _node_text(item)
            if t:
                return t
        return ""
    return _clean(value)


def _extract_identifier(value: Any) -> str:
    for item in _as_list(value):
        txt = _node_text(item)
        if txt:
            return txt
    return ""


def _looks_like_doi(value: str) -> bool:
    v = _clean(value).lower()
    if not v:
        return False
    if "doi.org/" in v:
        return True
    return bool(re.search(r"10\.\d{4,9}/\S+", v))


def _extract_identifier_prefer_doi(*values: Any) -> str:
    candidates: List[str] = []
    for value in values:
        for item in _as_list(value):
            txt = _node_text(item)
            if txt:
                candidates.append(txt)
    for c in candidates:
        if _looks_like_doi(c):
            return c
    return candidates[0] if candidates else ""


def _extract_keywords(value: Any) -> List[str]:
    if isinstance(value, str):
        if "," in value:
            return _dedupe([v.strip() for v in value.split(",")])
        v = _clean(value)
        return [v] if v else []
    if isinstance(value, list):
        return _dedupe([_node_text(v) for v in value])
    return []


def _author_name(node: Any) -> str:
    if not isinstance(node, dict):
        return _clean(node)
    given_raw = node.get("givenName")
    family_raw = node.get("familyName")
    if isinstance(given_raw, list):
        given = _clean(given_raw[0]) if given_raw else ""
    else:
        given = _clean(given_raw)
    if isinstance(family_raw, list):
        family = _clean(family_raw[0]) if family_raw else ""
    else:
        family = _clean(family_raw)
    if given or family:
        return f"{given} {family}".strip()
    return _clean(node.get("name"))


def normalise_ro_crate(data: dict, slug: str, repo: str) -> dict:
    """Normalise an RO-Crate JSON-LD graph into the common schema."""
    nodes = _index_graph(data)
    dataset = nodes.get("./")
    if not dataset:
        for node in nodes.values():
            node_type = _as_list(node.get("@type"))
            if "Dataset" in node_type:
                dataset = node
                break
    if not dataset:
        raise RuntimeError(f"RO-Crate missing Dataset root for {repo}")

    # Creators
    creators = []
    for cref in _as_list(dataset.get("creator")):
        cnode = _resolve_ref(cref, nodes)
        if not isinstance(cnode, dict):
            continue
        full = _author_name(cnode)
        if not full:
            continue
        orcid = _clean(cnode.get("@id")).replace("https://orcid.org/", "")
        creators.append({"full_name": full, "orcid": orcid})

    # Publication
    pub_node = _resolve_ref(_as_list(dataset.get("citation"))[0] if _as_list(dataset.get("citation")) else None, nodes)
    if not isinstance(pub_node, dict):
        pub_node = {}
    pub_authors = []
    for aref in _as_list(pub_node.get("author")):
        anode = _resolve_ref(aref, nodes)
        name = _author_name(anode)
        if name:
            pub_authors.append({"full_name": name})

    # Software from CreateAction instrument
    create_action = nodes.get("#datasetCreation")
    if not create_action:
        for node in nodes.values():
            if "CreateAction" in _as_list(node.get("@type")):
                create_action = node
                break
    instrument = _resolve_ref(create_action.get("instrument"), nodes) if isinstance(create_action, dict) else {}
    if not isinstance(instrument, dict):
        instrument = {}

    # Data/code references
    model_inputs = _resolve_ref(dataset.get("model_inputs"), nodes)
    if not isinstance(model_inputs, dict):
        model_inputs = {}
    model_code_inputs = _resolve_ref(dataset.get("model_code_inputs"), nodes)
    if not isinstance(model_code_inputs, dict):
        model_code_inputs = {}

    # Licence
    lic_ref = dataset.get("license")
    lic_node = _resolve_ref(_as_list(lic_ref)[0] if _as_list(lic_ref) else lic_ref, nodes)
    lic_url = _node_text(lic_node)
    lic_name = _clean(lic_node.get("name")) if isinstance(lic_node, dict) else ""

    # Funders
    funders = []
    for fref in _as_list(dataset.get("funder")):
        fnode = _resolve_ref(fref, nodes)
        fname = _clean(fnode.get("name")) if isinstance(fnode, dict) else _clean(fnode)
        if fname:
            funders.append({"name": fname})

    # Keywords
    keywords = _extract_keywords(dataset.get("keywords"))

    # Graphics
    graphics = fetch_graphics(repo)

    return {
        "slug": slug,
        "title": _clean(dataset.get("name")) or slug,
        "abstract": _clean(dataset.get("abstract")),
        "description": _clean(dataset.get("description")) or _clean(dataset.get("abstract")),
        "doi": _extract_identifier(dataset.get("identifier")),
        "creators": creators,
        "tags": keywords,
        "research_tags": keywords,
        "compute_tags": [],
        "publication": {
            "title": _clean(pub_node.get("name")) if isinstance(pub_node, dict) else "",
            "doi": _extract_identifier_prefer_doi(pub_node.get("identifier"), pub_node.get("@id"))
            if isinstance(pub_node, dict)
            else "",
            "journal": _node_text(pub_node.get("publisher")) if isinstance(pub_node, dict) else "",
            "date": _clean(pub_node.get("datePublished")) if isinstance(pub_node, dict) else "",
            "authors": pub_authors,
        },
        "software": {
            "name": _clean(instrument.get("name")),
            "doi": _extract_identifier_prefer_doi(instrument.get("identifier"), instrument.get("@id")),
            "url": _clean(instrument.get("url")) or _clean(instrument.get("codeRepository")),
        },
        "landing_image_url": graphics["landing_image_url"],
        "landing_image_caption": "",
        "model_setup_image_url": graphics["model_setup_image_url"],
        "model_setup_image_caption": "",
        "animation_url": graphics["animation_url"],
        "model_setup_description": "",
        "licence_url": lic_url if lic_url.startswith("http") else "",
        "licence_name": lic_name or lic_url,
        "dataset_nci_url": _clean(model_inputs.get("url")),
        "dataset_existing_id": _extract_identifier(model_inputs.get("identifier")),
        "dataset_notes": _clean(model_inputs.get("description")) or _clean(model_inputs.get("name")),
        "model_files_nci_url": _clean(model_code_inputs.get("url")),
        "model_files_existing_id": _extract_identifier(model_code_inputs.get("identifier")),
        "model_files_notes": _clean(model_code_inputs.get("description")) or _clean(model_code_inputs.get("name")),
        "credit_text": _node_text(dataset.get("creditText")),
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
        doi_display = (
            doi.replace("https://doi.org/", "")
            .replace("http://doi.org/", "")
            .replace("http://dx.doi.org/", "")
        )
    else:
        doi_display = (
            doi.replace("https://doi.org/", "")
            .replace("http://doi.org/", "")
            .replace("http://dx.doi.org/", "")
        )
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


def safe_doi(doi: str) -> str:
    """Return a DOI URL (add https://doi.org/ prefix if needed)."""
    if not doi:
        return ""
    if doi.startswith("http"):
        return doi
    if not _looks_like_doi(doi):
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

    # Landing image
    li_url = m["landing_image_url"] or PLACEHOLDER_IMG
    li_cap = m["landing_image_caption"] or ""
    anim_url = m.get("animation_url", "") or ""

    # Model setup image
    ms_url = m["model_setup_image_url"] or PLACEHOLDER_SETUP_IMG
    ms_cap = m["model_setup_image_caption"] or ""
    ms_desc = m["model_setup_description"] or ""

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

    if anim_url:
        lower_anim = anim_url.lower()
        if lower_anim.endswith((".mp4", ".webm", ".ogg")):
            snapshot_media_html = f"""
      <div class="full-width-image">
        <video controls loop muted playsinline style="width:100%; border-radius:6px;" onerror="this.outerHTML='<img src=&quot;{li_url}&quot; alt=&quot;{li_cap}&quot; style=&quot;width:100%; border-radius:6px;&quot; onerror=&quot;this.src=\\'{PLACEHOLDER_IMG}\\';\\' />';">
          <source src="{anim_url}">
        </video>
      </div>"""
        else:
            snapshot_media_html = f"""
      <div class="full-width-image">
        <img src="{anim_url}"
             alt="{li_cap}"
             style="width:100%; border-radius:6px;"
             onerror="this.src='{li_url}';" />
      </div>"""
    else:
        snapshot_media_html = f"""
      <div class="full-width-image">
        <img src="{li_url}"
             alt="{li_cap}"
             style="width:100%; border-radius:6px;"
             onerror="this.src='{PLACEHOLDER_IMG}';" />
      </div>"""

    return f"""---
# Generated by scripts/ingest_models.py — do not edit directly.
# Re-run the script to regenerate from {source_repo}
title: "{title}"
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
{snapshot_media_html}
      {f'<p style="font-size:13px; color:#777; text-align:center; margin-top:0.25rem;">{li_cap}</p>' if li_cap else ""}
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
      {f"<p>{ms_desc}</p>" if ms_desc else ""}
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

    img_url = m["landing_image_url"] or PLACEHOLDER_IMG
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
    cards_html = "".join(model_card_html(m) for m in models)

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
title: "Tag: {tag}"
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
title: "{name}"
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
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        registry = yaml.safe_load(f)

    entries = registry.get("models", [])
    print(f"Found {len(entries)} model(s) in registry.")

    models = []
    for entry in entries:
        slug = entry["slug"]
        repo = entry["repo"]
        print(f"\nIngesting: {slug} from {repo}")
        raw = fetch_ro_crate(repo)
        m = normalise_ro_crate(raw, slug, repo)
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
