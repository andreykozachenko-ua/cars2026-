#!/usr/bin/env python3
"""Builds ../catalog-leftnav-prototype.html from tree.json + top.json.

Real data source: live autodoc.co.uk page for BMW 3 Touring (F31) 328i xDrive,
car_id 59402, curled 2026-09-17. See README.md in this dir for the re-extraction
recipe (curl -> parse data-parent-id/data-subparent-id/data-category-id markup;
do NOT use text-extraction tools on this page, they truncate it).
"""
import json
import os

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SRC_DIR, "..", "catalog-leftnav-prototype.html")

with open(os.path.join(SRC_DIR, "tree.json"), encoding="utf-8") as f:
    tree = json.load(f)
with open(os.path.join(SRC_DIR, "top.json"), encoding="utf-8") as f:
    top = json.load(f)

# Drop the three "fake" pseudo-category sections (Tyres/wheels, Car accessories,
# Auto detailing & car care, Tools & equipment) that have no real flyout content
# on the live page -- they link straight out and have 0 nested categories.
real_sections = [s for s in tree if s["count"] > 0]

DATA_JSON = json.dumps({"sections": real_sections, "top": top}, ensure_ascii=False)

TEMPLATE_PATH = os.path.join(SRC_DIR, "template.html")
with open(TEMPLATE_PATH, encoding="utf-8") as f:
    template = f.read()

out = template.replace("__DATA__", DATA_JSON)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(out)

print(f"Wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)/1024:.0f} KB), "
      f"{len(real_sections)} sections, "
      f"{sum(s['count'] for s in real_sections)} categories, "
      f"{len(top)} top items")
