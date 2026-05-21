# Vehicle Selector + Autocomplete — `index-noplate.html` (as-built)

> **Status:** describes the **current implemented behaviour** of `index-noplate.html` (Variant B prototype, no plate lookup).
> Companion Confluence doc: `../confluence-vehicle-selector-initiative.txt`.
> Last verified against code: 2026-05-11.

---

## 1. Overview

A homepage widget + slide-in sidebar for vehicle identification. The user can either:
- **Type freely** in the autocomplete input → instantly select a car, or
- **Step through** Make → Model → Engine inside the sidebar.

All search and filtering is **client-side**. No backend search API.

---

## 2. Data Loading

On page init, three files are fetched in parallel:

| File | Size | Purpose | Required? |
|---|---|---|---|
| `cars_data.json` | ~3.6 MB | `MAKERS` list + `ALL_CARS` (~48k records) | Yes |
| `bmw.csv` | ~43 KB | Popularity ratings (currently **BMW only** in prototype) | Optional |
| `model_groups.json` | ~200 KB | TecDoc model family groupings | Optional |

If any optional file fails to load, the rest of the app still works (no ratings → all results rank equally; no groups → models render flat).

### 2.1 `cars_data.json` shape

```json
{
  "makers": [{ "id": 3854, "n": "BMW" }],
  "cars": [
    [
      3854,         // [0] maker_id
      44049,        // [1] model_id
      "3er (E46)",  // [2] model_name  — may include chassis code in parens
      152402,       // [3] car_id
      "320i",       // [4] trim_name
      "Petrol",     // [5] fuel_type   — may be null, may contain "/"
      1998,         // [6] year_from   — may be null
      2005,         // [7] year_to     — null = still in production
      105,          // [8] power_kw    — may be null
      143           // [9] power_hp    — may be null
    ]
  ]
}
```

### 2.2 `bmw.csv` shape

CSV with header. Each row: `car_id,"X,YY%"` (comma decimal). Parsed into a `RATINGS` `Map<car_id, float>`.

> **Prototype limitation:** in production this should be a full `car_ratings.json` covering all brands; the current prototype only ships ratings for BMW.

### 2.3 `model_groups.json` shape

```json
{ "44049": { "gid": 12, "gn": "3 Series" }, ... }
```

Key = model_id (string). Value = `{ gid: groupId, gn: groupName }`. Models without an entry are rendered ungrouped.

---

## 3. State Model

```js
state = { make: null, model: null, engine: null }   // 3 steps, no separate Year
selectedCar = null                                  // full car record once selected
stepHistory = []                                    // sidebar nav stack
currentStep = null                                  // 'make' | 'model' | 'engine'
```

`selectedCar` is set only when **all three** of make/model/engine are filled — i.e. the user has identified a unique car. Find Parts buttons are gated on this.

---

## 4. Query Pipeline (`runAc`)

```
raw input
   │
   ▼
[1] Min length check       q.length < 2  → hide dropdown, exit
   │
   ▼
[2] Normalise              deaccent (NFD strip) → lowercase
   │
   ▼
[3] Split separators       replace [-()_/] with space
   │
   ▼
[4] Letter+digit split     /([a-zA-Z]{3,})(\d)/g → "$1 $2"
                           "passat2018"  → "passat 2018"
                           "320d"        → "320d"   (only 1 letter group, untouched)
   │
   ▼
[5] Tokenise               split by whitespace
   │
   ▼
[6] Year extraction        any token matching /^(19|20)\d{2}$/ → yearFilter
                           remaining tokens → text terms
   │
   ▼
[7] Synonym expansion      each text token → termMatchers(t)
                           returns [{ str, re }] where re uses word boundaries
   │
   ▼
[8] Scan ALL_CARS          year filter:
                             skip if c[6] > yearFilter
                             skip if c[7] !== null && c[7] < yearFilter
                           text filter:
                             build 3 haystack variants (see §4.1)
                             every termForm group must match ≥1 of its synonyms
   │
   ▼
[9] Rank                   sort by RATINGS.get(car_id) descending
                           (missing rating → 0 → ranks last)
   │
   ▼
[10] Slice                 top 8 results
   │
   ▼
[11] Render                dropdown rows + "Showing top 8 of N" footer if N > 8
```

Input debounce: **150 ms** on both the widget input (`#searchInput`) and the sidebar input (`#sb-searchInput`).

### 4.1 Haystack construction

For each candidate car, three haystack variants are built and concatenated:

```js
base = deaccent(`${maker.n} ${c[2]} ${c[4]}`).toLowerCase()
                // makerName + modelName + trimName  (NOT fuel)
n1   = base.replace(/[-()_/]/g, ' ')        // "3er e46 320d"
n2   = base.replace(/[()_/]/g, ' ').replace(/-/g, '')  // "3ere46 320d"
n3   = n1.replace(/\b([a-z]) (\d+)\b/g, '$1$2')         // "a 4" → "a4"
hay  = n1 + ' ' + n2 + ' ' + n3
```

This lets `e46`, `e-46`, `e 46` and `a4` / `a 4` all match the same record.

> **Note:** the `fuel_type` field (`c[5]`) is **not** in the haystack. Fuel matching works because trim names themselves carry fuel codes (`320d`, `2.0 TDI`, etc.) and synonym groups expand them.

### 4.2 Synonym groups (in code)

| Category | Terms |
|---|---|
| Make alias | `vw`, `volkswagen` |
| Generation (Golf-style mk) | `mk1↔i`, `mk2↔ii`, `mk3↔iii`, `mk4↔iv`, `mk5↔v`, `mk6↔vi`, `mk7↔vii`, `mk8↔viii` |
| Body — estate | `estate`, `variant`, `touring`, `avant`, `sw`, `kombi`, `break`, `wagon` |
| Body — cabriolet | `cabriolet`, `cabrio`, `convertible`, `roadster`, `spider`, `spyder` |
| Body — coupe | `coupe`, `coupé` |
| Body — saloon | `saloon`, `sedan`, `berline`, `limousine` |
| Body — SUV | `suv`, `crossover` |
| Drive — 4WD | `4motion`, `quattro`, `xdrive`, `awd`, `4wd`, `4x4`, `syncro`, `allrad` |
| Fuel — diesel | `diesel`, `tdi`, `dci`, `hdi`, `cdti`, `cdi`, `jtd`, `d4d`, `tdci` |
| Fuel — petrol | `petrol`, `tsi`, `tfsi`, `fsi` |
| Fuel — hybrid | `hybrid`, `hev`, `phev`, `mhev` |
| Fuel — electric | `electric`, `ev`, `bev`, `e-tron` |
| Transmission | `auto`, `automatic`, `dsg`, `tiptronic`, `s-tronic`, `cvt`, `multitronic`, `pdk` |

### 4.3 Roman ↔ Arabic numerals

Bidirectional, full range **1..10**:

```
1↔i  2↔ii  3↔iii  4↔iv  5↔v  6↔vi  7↔vii  8↔viii  9↔ix  10↔x
```

Additionally, an `r`-prefixed digit (`r3`, `r5`) is treated as equivalent to its bare digit (`3`, `5`) — for chassis-code variants like Audi RS / R-series.

### 4.4 Term matching mode

For each token, `termMatchers(t)` returns:
- **Synonym group:** all group members with **word-boundary regex** (`(?:^|\s)term(?=\s|$)`) — prevents `auto` from matching `automatic`.
- **Roman numeral / r-prefix:** original + numeric form, both word-boundary.
- **Plain token:** plain `String.includes()` (no word boundary) — allows partial matches like `320` inside `320d`.

---

## 5. Dropdown UI

### 5.1 Row layout

```
┌─────────────────────────────────────────────────────────┐
│ 🖼  BMW 3er (E46) · 320i                          ›     │
│     1998–2005 · Petrol · 105 kW                         │
└─────────────────────────────────────────────────────────┘
```

| Element | Source | Notes |
|---|---|---|
| Thumbnail | `imageURL800/${car_id}.jpg`, 52×36 | `setBgImg()` probes load; falls back to `uploads/000.jpg` |
| Main line | `${maker.n} ${c[2]} · ${c[4]}` | Matched tokens wrapped in `<span class="hl">` (orange `#F85A00`, bold) |
| Sub line | `[year_range, fuel_before_slash, "${kW} kW"]` joined by ` · ` | **kW only, no hp** |
| Chevron | `›` | Decorative |

### 5.2 States

| State | Render |
|---|---|
| `q.length < 2` | dropdown hidden |
| No matches | `<div class="ac-more">No vehicles found</div>` |
| `total ≤ 8` | rows only |
| `total > 8` | rows + `<div class="ac-more">Showing top 8 of N — refine your search</div>` |

### 5.3 Closing the dropdown

A global `click` listener on `document` closes both dropdowns (`#acDrop`, `#sb-acDrop`) when the click is outside any `.ac-wrap`.

### 5.4 Keyboard navigation

> **Not implemented.** Mouse / touch only. No `↑ ↓ Enter Esc` handling in current prototype.

---

## 6. Selecting an Autocomplete Result (`pickAc`)

1. Find the full car record by `car_id`.
2. Hide both dropdowns (`#acDrop`, `#sb-acDrop`).
3. Clear both inputs (`#searchInput`, `#sb-searchInput`).
4. Set `state = { make: c[0], model: c[1], engine: c[3] }`.
5. Fill all three step rows: Make / Model / Engine values + filled style.
6. Call `setSelectedCar(car, null)`:
   - `selectedCar = car`
   - Enables both Find Parts buttons (`#findBtn`, `#sidebarFindBtn`)
   - Saves to recent-vehicles history (localStorage, see §9)
   - Re-renders sidebar history list

> **Known gap vs Confluence spec §5:** `pickAc` does **not** auto-close the sidebar when triggered from the sidebar input. Engine selection via the step flow (`pickItem`, step=engine) **does** auto-close after 120 ms.

---

## 7. Sidebar — Layout & Navigation

### 7.1 Structure

```
┌── topbar ──────────────────────────────────┐
│ [back?]  Select Your Vehicle         [×]   │
├── panel-main ──────────────────────────────┤
│  search input  (auto-focused on open)      │
│  ───── or select step by step ─────        │
│  Make    | Select               ›          │
│  Model   | Select               › (disabled until Make)
│  Engine  | Select               › (disabled until Model)
│  Recent vehicles (hidden if empty)         │
├── panel-step (slides over panel-main) ─────┤
│  [chip] [chip]                             │
│  Step N of 3 · Select <stage>              │
│  ─ sticky search ─                         │
│  list of options                           │
├── footer ──────────────────────────────────┤
│  [ Find Parts ]  (disabled until complete) │
└────────────────────────────────────────────┘
```

- Width: **500 px** on desktop; `100%` below 480 px.
- Overlay: `rgba(0,0,0,.5)`, fades in 300 ms; click closes sidebar.
- Slide-in: `transform: translateX(100%) → 0`, 350 ms `cubic-bezier(.32,.72,0,1)`.
- Search input is focused **350 ms** after sidebar opens (post-animation).

### 7.2 Panel transitions

- Step panel slides in from the right; main panel is pushed left by `-30%` (parallax effect), `transform`, 320 ms.
- Within the step panel, content transitions on next/back use a 48 px translate + opacity fade (180 ms exit → swap → enter).
- Back chevron appears only when step panel is active.

### 7.3 Step rows in main panel

| Row | Enabled when | Click behaviour |
|---|---|---|
| Make | Always | Opens Step 1 |
| Model | After Make filled | Opens Step 2 |
| Engine | After Model filled | Opens Step 3 |

Clicking a **filled** row resets that row and everything below it (`state[s..] = null`), then opens the step panel for that step.

### 7.4 Breadcrumb chips (trail)

In the step panel, chips show **previously filled steps lower than `currentStep`**. Click → `jumpToStep` resets that step + subsequent steps + animates back to that step.

---

## 8. Step Panels

### 8.1 Step 1 — Make

- All makers from `MAKERS`, sorted alphabetically by name.
- No grouping. Single flat list.
- Filter: search by maker name (case-insensitive substring).

### 8.2 Step 2 — Model

Unique `model_id` for the selected make is collected from `ALL_CARS`.

- **Default view (no filter):** models grouped using `MODEL_GROUPS`.
  - Group = TecDoc family. Group header shows family name + count badge.
  - Groups are sorted alphabetically; models within a group sorted alphabetically.
  - A group with a single model renders as a flat row (no accordion).
  - A group containing the currently selected model auto-opens and gets `.has-sel` orange highlight.
  - Models with no `MODEL_GROUPS` entry render as ungrouped flat rows **after** the groups.
- **Filtered view (user types):** flat list, filter applied via case-insensitive `includes` on label + sub.

### 8.3 Step 3 — Engine / Trim

All engines for the selected `model_id` from `ALL_CARS`.

- Grouped by `fuel_type` (`c[5].split('/')[0].trim()` → first token before slash; `null` → "Other").
- Groups sorted **by count descending** (most common fuel first).
- All groups open by default.
- Each row shows:
  - **Name:** `c[4]` (trim name)
  - **Sub:** `[fuel, "${kW} kW / ${hp} hp", year_range]` joined by ` · `

> **Spec note:** the Confluence doc §7 calls for a fixed order Petrol → Diesel → Hybrid → Electric. The prototype sorts by count; this is a known divergence to reconcile.

### 8.4 Selecting an item (`pickItem`)

| Step | Behaviour |
|---|---|
| `make` | Set `state.make`, reset model + engine, fill Make row, **auto-advance to Model step** |
| `model` | Set `state.model`, reset engine, fill Model row, **auto-advance to Engine step** |
| `engine` | Set `state.engine`, fill Engine row, call `setSelectedCar`, **auto-close sidebar after 120 ms** |

### 8.5 Step search

- Sticky search input at top of step panel.
- Debounce: **120 ms**.
- Filter: case-insensitive `includes` on label + sub.
- When filtered, model/engine grouping is bypassed (flat list).

---

## 9. Recent Vehicles

| Property | Value |
|---|---|
| Storage | `localStorage` |
| Key | `sb_recent_cars` |
| Max entries | 5 |
| Trigger | Saved on every `setSelectedCar` |
| Render location | Sidebar main panel (`#sb-recent-section`), hidden if empty |
| Entry fields | `{ id, make, model, trim, year, yearTo, fuel, kw }` |
| Pick action | `pickRecent` → set state, fill rows, close sidebar |
| Remove button | **Not rendered** (CSS exists but `renderSbHistory` does not emit it) |

Duplicate insertions are de-duped by `id` (most-recent-first).

---

## 10. Find Parts Button

| Property | Value |
|---|---|
| Element 1 | `#findBtn` — in the widget |
| Element 2 | `#sidebarFindBtn` — in the sidebar footer |
| Label | `"Find Parts"` (the sidebar footer initially renders `"Search"` in HTML but JS overwrites on first init) |
| Colour | `#0068d7` (active) / `#ddd` (disabled) |
| Enabled when | `selectedCar !== null` (all 3 steps complete) |
| Click handler | `findParts()` → `alert(...)` (prototype mock, would navigate to catalogue) |

---

## 11. Widget States (Step-entry Card)

| State | Trigger | Title | Sub | Image |
|---|---|---|---|---|
| Empty | `!state.make` | `"Select by Make, Year, Model..."` | `"Make › Model › Engine"` | `uploads/000.jpg` |
| Partial — Make only | `state.make`, `!state.model` | `"${maker} — select model"` | `"Make › Model › Engine"` | placeholder |
| Partial — Make + Model | `state.model`, `!state.engine` | `"${maker} ${model} — select engine"` | `"Make › Model › Engine"` | placeholder |
| Complete | `state.engine` | `"${maker} ${model}"` | `"${trim} · ${year_range}"` | `imageURL800/${car_id}.jpg` |

`updateStepEntryCard()` is invoked from `updateSelectorBtn()` which fires on every state mutation.

---

## 12. Hidden / Unused Code

These elements exist in the prototype but are intentionally not exposed in the current Variant B UI:

| Element | Status |
|---|---|
| `#makerShortcuts` (top-10 maker chips) | Rendered into a `display:none` container — not visible |
| `#widgetMakerShortcuts` | Referenced in `renderMakerShortcuts` but element does not exist in DOM |
| `#recentSection` in widget (not sidebar) | Inline `display:none` — recent vehicles live in sidebar only |
| `NUM2ROM3` / `ROM2NUM3` constants | Defined but never read (full 1..10 map is used) |
| `.recent-item-remove` button styling | CSS present, button not rendered |

---

## 13. Known Divergences from Confluence Spec

| # | Spec (`confluence-vehicle-selector-initiative.txt`) | Prototype reality |
|---|---|---|
| 1 | Synonym groups list (§5) | Adds `vw/volkswagen` and `mk1..mk8 ↔ i..viii`; omits `van` and `lpg` groups |
| 2 | Roman/Arabic — bidirectional case-insensitive (§5) | Full 1..10 + `r`-prefix variant |
| 3 | Step 3 fuel ordering: Petrol → Diesel → Hybrid → Electric (§7) | Ordered by count descending |
| 4 | Autocomplete pick from sidebar closes sidebar (§5) | Does **not** close sidebar |
| 5 | Result subtitle: `Year range · Fuel · Power in kW` (§5) | Same fields; **kW only**, no hp |
| 6 | Ratings from `car_ratings.json` (§10 open question) | Currently `bmw.csv`, BMW only |
| 7 | Keyboard navigation not in spec; expected from accessibility | Not implemented |
| 8 | Maker shortcuts | Not in spec; code renders chips but container hidden |

---

## 14. Files Kept In Sync

The autocomplete + selector code is duplicated across several prototype HTML files. Edits to one must be propagated:

- `index.html` (main, with plate)
- `index-noplate.html` (Variant B — this doc's reference)
- `index-no-reg.html`
- `index-3step.html`
- `ios-prototype.html`
- `prototype-v2.html`
- `sidebar-prototype.html`

---

## 15. Local Dev

```
cd /Users/andriikozachenko/CARS/cars_privat
npm run admin     # serves on http://localhost:3001
```

Open `http://localhost:3001/index-noplate.html`.
