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

## Mobile app-style drilldown (2026-09-18, local only)

Replaced the mobile rendering of **New mode**'s two-column hover-nav+panel
(the thing flagged as an open question in the mobile pass above) with a
native-app-style drilldown, matching two reference screenshots of the actual
Autodoc mobile app: a parent screen (large image + bold name + chevron, one
per full-width card) that pushes to a category screen (back arrow + pill
showing the parent name + flat list rows with smaller images, thin dividers,
small gray group-subtitle labels). Tapping a leaf category uses the real
listing link, same as everywhere else in this prototype.

- Only replaces **New mode** below the existing 900px breakpoint —
  `.new-layout{display:none}` / `.mCatalog{display:block}` in that media
  query. Desktop New mode and **both breakpoints of Old mode** (the grid+flyout
  emulation of the current site) are untouched.
- Markup: `#mCatalog` holds two `.mScreen` divs (`#mScreenParents`,
  `#mScreenCategory`), toggled via `hidden`, not re-rendered from scratch on
  back — `openMobileSection(sectionId)` just repopulates `#mCategoryList` and
  flips visibility.
- Deliberately dropped the item-count badge that the desktop `navrow` shows
  next to each parent name — the reference app screenshots don't have it, and
  matching the reference took priority over information density here.
- Icons reused as-is from the existing `ICON()` CDN helper — no new asset
  source, just bigger sizes (150px card icons vs 100px flat-list icons) to
  match the app's proportions.
- **Local only, not deployed** — explicitly requested to stay local this round.

**Regression fixed same day:** the first cut of this drilldown replaced the
working "Quick search by category" input with a purely decorative
`<div class="mBar__pill">` (no `<input>` inside) on the mobile parent screen —
so search silently stopped doing anything on mobile once this shipped. Fixed
by putting a real `<input id="mSearch">` inside the pill and wiring it to
`renderMobileParents(filterText)`, which reuses the same `sectionMatches(s, f)`
predicate the desktop nav search already used (extracted from `renderNav`'s
inline logic so both call sites share one implementation) — matches by
section name OR any nested category name, shows `#mParentEmpty` when nothing
matches. Lesson: when a screenshot-matching pass replaces a whole markup
block wholesale, re-check that every element carrying real interactivity in
the old version has an equivalent in the new one, not just the visual layout.

**Second regression, same root cause:** search also didn't work one level
deeper — the category screen's pill (`#mCategoryTitle`) was a static `<b>`
label, not editable, matching the reference screenshot's *look* but not its
*behavior* (the reference shows the section name sitting in an editable
search field). Fixed by making it a real `<input id="mCategorySearch">`,
pre-filled with the section name on open (cosmetic parity with the
screenshot) but rendering the **full unfiltered** list initially — filtering
only kicks in once the user actually edits the text. `renderMobileCategoryList(sectionId, filterText)`
filters items within the open section's groups and hides any group whose
items all get filtered out; shows `#mCategoryEmpty` on zero matches.

**Search results upgraded to show categories, not sections (same day):**
the parent-screen search originally just filtered which *parent cards*
stayed visible (via `sectionMatches`), so a query like "oil filter" surfaced
whole sections ("Car service parts", "Engine"...) the user then had to
re-open and re-scan. Changed `renderMobileParents(filterText)` so a non-empty
query switches `#mParentList` to the flat `.mList--flat` style and renders
**deduped leaf categories directly** (same cross-section dedup-by-`category_id`
approach as the desktop panel search) — tapping a hit goes straight to its
real listing link. Empty query still shows the normal parent cards.

## Not deployed

Kept local only, consistent with the rule in `reference_prototypes_deploy`
memory — real licensed catalog structure + real vehicle photo, not demo data.
