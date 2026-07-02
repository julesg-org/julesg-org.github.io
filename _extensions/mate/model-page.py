#!/usr/bin/env python3
"""
_extensions/mate/model-page.py — Pandoc filter for M@TE model pages
===================================================================
Reads model data from QMD YAML frontmatter (under `model:` key) and
generates the full model page HTML at render time via model_renderer.

Usage (in _quarto.yml):
  filters:
    - _extensions/mate/model-page.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from scripts.model_renderer import render_model_page


def _stringify(inlines):
    """Recursively extract plain text from pandoc Inline elements."""
    result = []
    for item in inlines:
        if isinstance(item, list):
            result.append(_stringify(item))
            continue
        if not isinstance(item, dict):
            result.append(str(item))
            continue
        t = item.get("t")
        c = item.get("c")
        if t in ("Space", "SoftBreak", "LineBreak"):
            result.append(" ")
            continue
        if c is None:
            continue
        if t == "Str":
            result.append(c)
        elif t == "Code":
            result.append(c[1] if isinstance(c, list) and len(c) > 1 else str(c))
        elif t == "Math":
            result.append(c[1] if isinstance(c, list) and len(c) > 1 else str(c))
        elif isinstance(c, list):
            result.append(_stringify(c))
        else:
            result.append(str(c))
    return "".join(result)


def _meta_to_python(val):
    """Recursively convert a pandoc MetaValue to a plain Python object."""
    t = val["t"]
    c = val["c"]
    if t == "MetaString":
        return c
    if t == "MetaBool":
        return c
    if t == "MetaList":
        return [_meta_to_python(v) for v in c]
    if t == "MetaMap":
        return {k: _meta_to_python(v) for k, v in c.items()}
    if t == "MetaInlines":
        return _stringify(c)
    return ""


if __name__ == "__main__":
    doc = json.load(sys.stdin)
    meta = doc.get("meta", {})

    if "model" in meta:
        model_data = _meta_to_python(meta["model"])
        if "title" in meta:
            model_data["title"] = _meta_to_python(meta["title"])
        html = render_model_page(model_data)
        doc["blocks"] = [{"t": "RawBlock", "c": ["html", html]}]

    json.dump(doc, sys.stdout)
