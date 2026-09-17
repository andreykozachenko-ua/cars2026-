# Catalog left-nav UX prototype — build sources

Builds `../catalog-leftnav-prototype.html`: a standalone comparison of the
**current** parent-category grid (click a tile → flyout tooltip) against a
**proposed** left-side vertical menu (hover a parent → nested categories render
in a panel on the right), on the same real catalog data.

Vehicle: BMW 3 Touring (F31) 328i xDrive, car_id 59402, curled from
`autodoc.co.uk/spares/bmw/3er-reihe/3-touring-f31/59402-328-i-xdrive` on
2026-09-17.

## Rebuild

```bash
cd /Users/andriikozachenko/CARS/cars_privat/catalog-leftnav-src
python3 build.py
```

## Files

| File | What it is |
|---|---|
| `template.html` | The prototype. `__DATA__` is the injection point (sections + top items JSON). Edit this for any markup/CSS/JS change. |
| `build.py` | Drops the 0-item pseudo-sections... actually keeps all sections with `count > 0` (all 35 real ones, including the 3 fake/pseudo tiles that do have real flyout content: Tyres/wheels, and any others that turned out non-empty on this car) and injects them + `top.json` into the template. |
| `tree.json` | 38 raw parsed sections (name, real listing links, `category_id` per item, `subtitle` groups) from the live page. |
| `top.json` | The 40 real items from the "Top parts categories for..." personalized block — left untouched in the prototype. |
| `car.jpg` | Vehicle photo, copied from `../imageURL800/59402.jpg`. Referenced by the built HTML as `catalog-leftnav-src/car.jpg` (relative to `../catalog-leftnav-prototype.html`) — keep this file here, don't move it. |

## Re-extracting the tree from a live page

```bash
curl -sS -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36" \
  -o page.html "https://www.autodoc.co.uk/spares/<make>/<range>/<model>/<car_id>-<engine>"
```

Then parse (see the parser embedded in this session's history, or rewrite):
- Main catalog region is between the h2 `"Please select the appropriate car parts category..."`
  and the h2 `"Discover practical and stylish..."` (accessories section).
- Each section = `<div class="catalog-items" id="{parent_id}" data-catalog ... data-parent-id="{parent_id}">`.
  Marker order inside a section's attributes is **not fixed** (`data-link`,
  `data-tecdoc-catalogue-child`, `data-parent-id`, `data-category-id` can appear
  in any order) — match each attribute independently, don't assume a fixed regex order.
- Inside the tooltip (`catalog-items__tooltip-wrap`), children alternate between
  `catalog-items__tooltip-subtitle` (ЛО group headers, `data-subparent-id`) and
  `catalog-items__tooltip-link` (leaf categories, `data-category-id` + `data-link`
  + name in the **last** `<span>` inside the block — earlier prototypes' pattern
  of "name in a plain trailing span" still holds even though some sections wrap
  the icon in `<a>` and others in `<span role="link">`).
- Icons: `https://scdn.autodoc.de/catalog/categories/{size}x{size}/{id}.png` for
  both section icons (id = parent_id) and category icons (id = category_id).
- Top-categories block: `id="top-categories"` section, items have
  `data-category-id`, `data-category-name`, `data-link` (order-independent again).
- **Do not** use WebFetch-style text extraction on this page — it truncates
  large pages and silently drops sections (same caveat as the Kia audit in
  `../catalog-prototype-src/`).

## What's real vs demo

Everything is real: section names/order, all 973 (this car) category names,
their live listing URLs, ЛО group headers, category/section icons, the top-40
personalized block, and the vehicle photo. **Nothing is synthesized** in this
prototype (unlike `../catalog-prototype-src/`, which has fake prices/counts) —
the only "demo" simplification is cosmetic: the old-grid flyout expands inline
under the tile row instead of as a tooltip anchored to the clicked icon.

## Design decisions worth keeping

1. **Hover activates, click pins.** `pinned` flag in `template.html` — once a
   user clicks a row, mouseenter on other rows stops auto-switching the panel,
   so touch/keyboard users (and anyone who wants to stop and read) aren't
   fighting a panel that changes under their cursor.
2. **Search must dedupe by `category_id`.** Same finding as
   `../catalog-prototype-src/README.md`: ~558/693 categories (Kia numbers;
   similar ratio here) are deliberately cross-listed across multiple parent
   sections, so an un-deduped search shows "Brake pads" 2-3x. Fixed with a
   `Set` on `category_id` in `renderPanel()`.
3. **Left column was already there and mostly empty** — the live page's
   `#catalog` section is already a `col-lg-4 / col-lg-8` grid; the left third
   currently holds only the "Quick search by category" box with a lot of dead
   space below it. The left-nav menu fills space that already exists in the
   real layout, it isn't a net-new column.

## Mobile pass (2026-09-17)

Checked at 390×844 (iPhone-class viewport) via Playwright. Three real bugs found and fixed, not just cosmetic:

1. **Missing `<meta name="viewport">`** — the page rendered at a fixed 980px desktop layout and got scaled down by the browser instead of actually reflowing. Every responsive media query in the CSS was silently inert until this was added.
2. **`.new-left{position:sticky}` doesn't degrade on mobile.** On the single-column mobile stack, the sticky nav box doesn't sit beside the panel — it stays pinned over the top of the viewport and visually covers the first ~700px of the right panel's content once you scroll past it. Fixed with `.new-left{position:static !important}` inside the existing `@media (max-width:900px)` block, plus capped `.navlist{max-height:360px}` there so the list itself is a short scrollable box instead of stretching the page.
3. **Tap-to-result distance.** Even after the sticky fix, the left-nav pattern inherently stacks "all 35 rows" above "selected section's content" on narrow screens, so a tap on row 3 still leaves the result below the fold. The **old grid** doesn't have this problem — its flyout opens inline right after the tapped tile, so proximity between tap and result is near-zero regardless of screen width. Compensated (not fully solved) by auto-scrolling `rightPanel` into view on tap when `matchMedia('(max-width: 900px)')` matches — desktop hover behavior is untouched since the media query gate is mobile-only.

**Open question for a real mobile design** (not resolved by this patch, worth raising if this direction is pursued for a phone-first shop): should mobile drop the side-panel metaphor entirely and use a **tap-to-expand accordion** instead (categories insert directly under the tapped row, like the old grid already does), rather than porting the desktop hover-panel layout as-is? The current fix makes the desktop pattern *usable* on mobile, not necessarily the *right* pattern for mobile.

## Not deployed

Kept local only, consistent with the rule in `reference_prototypes_deploy`
memory — real licensed catalog structure + real vehicle photo, not demo data.
