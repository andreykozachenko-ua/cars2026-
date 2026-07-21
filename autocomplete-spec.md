# Vehicle Selector + Autocomplete — `index-noplate.html` (as-built)

> **Status:** describes the **current implemented behaviour** of `index-noplate.html` (Variant B prototype, no plate lookup).
> Companion Confluence doc: `../confluence-vehicle-selector-initiative.txt`.
> Last verified against code: 2026-07-21.

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
[8b] Fuzzy maker fallback  ONLY if step [8] found zero matches — see §4.5
   │
   ▼
[9] Rank                   relevanceScore(c, tt) — RATINGS.get(car_id) plus a
                           model/maker-match boost (see §4.6), descending
   │
   ▼
[10] Slice                 top 20 results
   │
   ▼
[11] Render                dropdown rows + "Showing top 20 of N" footer if N > 20
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
- **Plain token:** alphanumeric-boundary regex `abRe` (`(?:^|[^a-z0-9])term(?=[^a-z0-9]|$)`) — **as of 2026-07, this applies to every token length, including single characters.**

> **2026-07 fix:** single-character tokens used to skip the boundary check and fall back to plain `String.includes()`, making them near-useless as filters (e.g. `"e"` matched almost any haystack, since nearly every string contains the letter "e" somewhere). This broke real queries like `mercedes e-klasse`, which tokenizes to `["e","klasse"]` — the dropdown mixed in S-Klasse/G-Klasse/T-Klasse because `"klasse"` alone was doing all the filtering. Fixed by dropping the length exception so single chars also require a clean boundary (e.g. `"e"` only matches a standalone `e`, such as the one in `e-klasse`).
>
> **Related fix in `normEng`** (used to normalize split engine codes like `"320 d"` → `"320d"`): it was also merging a real 4-digit year with a following single letter — `"2023 e"` (year, then "E" from a later "E-Klasse" in the same query) became `"2023e"`, which fails the year regex and matches nothing. Fixed by skipping the merge when the digit group is itself a `19xx`/`20xx` year.

### 4.5 Fuzzy maker-typo fallback (added 2026-07-21)

If step [8] finds **zero** matches, `runAc` tries once more with each token replaced by its closest maker-name word (if any is close enough), before giving up and showing the empty state.

```
MAKER_WORDS   = every word (≥3 chars) from every MAKERS[].n, deaccented + lowercased
                — built once at load (buildMakerWords()), ~200 words, not the 48k-record haystack

fuzzyMakerWord(tok):
  skip if tok.length < 3, non-alphabetic, or already an exact maker word
  maxDist = tok.length <= 5 ? 1 : 2
  return the closest MAKER_WORDS entry within maxDist, else null (Damerau-Levenshtein — see below)
```

- **Damerau-Levenshtein, not plain Levenshtein.** An adjacent-letter transposition (`"ADUI"` vs `"AUDI"`) is distance **1** under Damerau-Levenshtein (one transposition) but distance **2** under plain Levenshtein (two substitutions) — the whole point of this fallback is catching exactly that typo shape, so plain Levenshtein under-corrects it.
- **Only a fallback** — runs after the normal pipeline already returned zero results, and only touches tokens that don't already match a real maker word. Queries that already work are completely untouched (confirmed: zero metric change on any non-typo query variant in `autocomplete-tests/`).
- If the corrected re-run finds results, the dropdown shows a hint above the list: `Showing results for AUDI` (blue, `#0068d7`) — see `correctionHtml` in `runAc`.
- **Cost:** roughly 2x a normal query when it fires (a second full `ALL_CARS` pass with the corrected token) — 5-15ms in absolute terms on this dataset, not perceptible on its own. See §4.5.1 for a much larger, unrelated cost this fallback exposed.
- **Guard against over-correcting real words** (added same day, 2026-07-21): `fuzzyMakerWord(t)` finds the *closest* maker word within range regardless of whether `t` is already a real word that happens to live near an unrelated maker name — e.g. `"spider"` (Alfa Romeo Spider) is distance-2 from the real maker `"SPYKER"`, `"partner"` (Peugeot Partner) from `"PANTHER"`, `"xantia"` (Citroën Xantia) from `"LANCIA"`, `"triton"` (Mitsubishi Triton) from `"PROTON"`, `"max"` (Isuzu D-Max) from `"MAN"`. Applying the fuzzy check to *every* token (needed, since we don't know in advance which token is the actual typo) kept silently mangling a perfectly good model-name word into an unrelated maker, which then failed to match anything — the "fixed" query still returned zero results, just for a different reason. Fixed by only accepting a fuzzy correction when the original token doesn't already match *anything* in `ALL_CARS` on its own (checked via the same `termMatchers`/haystack test used by the main filter) — a token that's already valid somewhere isn't the thing that broke the query, so leave it alone.
- **Known gap:** doesn't help when the typo shifts a word boundary in a multi-word maker (`"ALFA ROMEO"` → `"ALF AROMEO"` tokenizes wrong before the fuzzy check even runs).
- Measured impact (1659-query synthetic suite, `autocomplete-tests/`): `make_typo` variant zero-result rate 99.6% → 8.2% (first pass, maker-only correction) → **1.4%** (after the over-correction guard above). Top-1 0.4% → 31.2% → 32.6%. See `project_autocomplete_testing` memory for the full report.

#### 4.5.1 Perf trap this fallback exposed (found + fixed same day)

A fuzzy-corrected **maker-only** query (e.g. `"mersedes"` → `"mercedes"`, no model/trim typed) leaves `res` as almost the *entire* catalog for a large maker — thousands of records, unconstrained by any other token. `getRefineSuggestions()` (see §12, `.ac-refine`) was still being called whenever `res.length > 20` to build markup for a chip row that's been `display:none` since before this fix — and its `countAfterTerm()` calls are `O(res.length)` **per candidate**, with candidates generated per unique trim/year/displacement in `res`. On a few thousand unconstrained Mercedes records this took **~2.5 seconds** per keystroke (measured via `performance.now()` around `runAc()` in a real headless browser) for markup nobody ever sees. Fixed by skipping the call entirely (`if (false && res.length > 20)` in `runAc` — left as dead code rather than deleted, in case the refine-chip UI is ever un-hidden). Confirmed fix: 2500ms → 17ms on the same query; zero change to `autocomplete-tests/` metrics (that computation never touched `res`/ranking, only unused markup).

> **Lesson for future perf work on this file:** a "2x slower" estimate from reading a diff would have missed this — the real cost was ~150x, sitting in unrelated legacy code that a new code path happened to newly exercise. Profile with `page.evaluate(() => { performance.now(); runAc(q, dropId); })` in a real browser, by keystroke-prefix, before trusting a theoretical estimate.

### 4.6 Relevance ranking (`relevanceScore`)

Sort key is not raw popularity alone:

```js
function relevanceScore(c, tt) {
  if (!tt.length) return RATINGS.get(c[3]) || 0;
  const makerModel = `${maker} ${c[2]}`.toLowerCase();
  const modelWords = c[2].toLowerCase().split(/[\s\-()]+/).filter(Boolean);
  let boost = 0;
  if (modelWords.some(w => w === tt[tt.length-1])) boost += 2.0;   // last typed token is an exact model word
  if (tt.every(t => makerModel.includes(t))) boost += 1.0;         // every token appears in maker+model text
  return (RATINGS.get(c[3]) || 0) + boost;
}
```

Sorted descending: `res.sort((a,b) => relevanceScore(b, tt) - relevanceScore(a, tt))`. A car with no rating but a strong token-boost can still outrank a highly-rated but loosely-matching one.

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

Implemented via `handleAcKeydown(e, dropId)` (per-dropdown state in `AC_STATE[dropId].focusIdx`):

| Key | Behaviour |
|---|---|
| `↓` ArrowDown | Move focus to next item (wraps) |
| `↑` ArrowUp | Move focus to previous item (wraps) |
| `Enter` | `pickAc()` on the focused item (or the first item if none focused) |
| `Escape` | Hide dropdown, reset focus index, dismiss ghost suggestion |
| `→` ArrowRight / `Tab` | Accept the inline ghost-text suggestion (only when caret is at the end of the input and a suggestion is showing) — see §5.5 |

> This section previously said keyboard nav was not implemented — that was stale; `handleAcKeydown` predates the ghost-text work below.

### 5.5 Inline ghost-text suggestions (added 2026-07)

While typing, a grey completion is rendered inline in the input (after the typed text, prefixed with a small orange `+`), suggesting the next thing worth typing. Accept with `→`/`Tab`, dismiss with `Esc`, outside click, or picking a result.

**Markup:** `.ac-box` now wraps the `<input>` in a `.ac-input-wrap` alongside a sibling overlay `<div id="searchInput-ghost">` (and `sb-searchInput-ghost` for the sidebar copy), absolutely positioned over the input. The overlay is `<span class="ac-ghost-typed">` (transparent, mirrors the typed text for alignment) + `<span class="ac-ghost-plus">` + `<span class="ac-ghost-suggest">`.

**Source — a fixed staged funnel** (`getStagedTip(res, yf)`), not a generic "best narrowing tip":

```
model  →  year  →  fuel type  →  engine/trim
```

> **2026-07:** the funnel used to start with a separate **model group** stage (`groupTextVariants()` + `MODEL_GROUPS` tally, suggesting the *group name* itself, e.g. `"3er"`). Removed as its own stage — group names rarely matched the searchable text cleanly and the fallback-text guessing produced suggestions that felt arbitrary. `MODEL_GROUPS` came back on 2026-07-21 in a different role (see point 2 below) — it's used to *tally* significance, but the thing actually suggested is always a real literal model name, never the group label. It's also unaffected in its original job of grouping the dropdown's default/no-filter view (§7).
>
> **2026-07-21: model moved before year.** It used to be year → model → fuel → trim, contradicting both this doc and plain UX sense — right after typing just a maker name, a bare year (`"+2020"`) is a much weaker guess than a popular model (`"+3"`); year only earns its keep as a disambiguator *once* a model is already pinned down (it mostly maps to generation/fitment at that point). Swapped the block order in `getStagedTip`.

1. Only fires once a **single maker dominates** the current result set (`count / res.length >= 0.5`, factored out as `dominantMakerOf(res)`) — needed because this dataset splits some brands into sub-entries (`FORD`, `FORD USA`, `FORD OTOSAN`, `FORD ASIA / OCEANIA` all match `"ford"`).
2. Each stage tallies within that dominant maker's subset and stops at the **first** stage with real ambiguity — it does not compute all 4 and rank them. **Model stage tallies by `MODEL_GROUPS` nameplate (`gid`), not raw `model_id`** (fixed 2026-07-21) — TecDoc gives each *generation* its own `model_id` (BMW's "3" alone is 5+ ids: E36/E46/E90/F30/G20), which fragmented a popular maker's records across 100+ tiny buckets and made every single one of them miss the 3%-of-total significance bar below (BMW's single largest `model_id` bucket was 65/2360 = 2.75%, just under the line) — **the model stage silently never fired for exactly the highest-search-volume makers** (BMW, Audi, VW, Toyota, Ford, Mercedes all affected; small-catalog makers like Smart/Lada/Seat were unaffected and already worked). Tallying by nameplate group first restores enough count-per-bucket to clear the bar; the candidate text actually suggested is still the most popular *literal* model name within that group (e.g. `"3 (E90) Limousine"`), picked via the same validation as any other stage — never the bare group name, to avoid resurrecting the exact problem that killed the original model-group stage above.
3. `significantEntries()` guards every stage: if the top candidate already covers ≥90% of the tally, treat the stage as resolved (nothing to suggest, move on); otherwise drop anything below ~3% of the total. This exists because free-text AND-matching occasionally lets a stray record slip in that satisfies every token for the wrong reason (e.g. a lone BMW "501" classic matching a loose digit token, or a Mercedes "C 300 e" hybrid matching both `"e"` and `"klasse"`) — without the filter, that noise could outrank the real answer. **Caveat:** this same 3%-style bar is what caused point 2's bug — when reusing `significantEntries` for a new tally, check whether the tallying key is more fragmented than what it was calibrated for; aggregate at a coarser existing grouping rather than lowering the threshold (which would just let noise back in where the threshold already worked fine).
4. Year stage is skipped once a year token is already in the query.

### 5.5.1 Mid-word model completion (added 2026-07-21)

Separate from the append-style funnel above (which fires once a word is *finished*, i.e. the raw input ends in whitespace): while the user is still mid-typing a model-name token right after a resolved maker (raw input has **no** trailing space, ≥2 tokens typed), a grey completion of the *current* word appears — same rendering mechanic as the zero-results maker completion below (glued tail, no `+`, no leading space), not the funnel's append style.

```
"VW gol"        → completes to "golf"
"AUDI a"        → completes to "avant"
"MERCEDES e-kl" → completes to "klasse"   (hyphenated sub-token handled)
"AUDI a4"       → no completion — "a4" is already a complete/matched token, falls through to the append funnel instead
```

- `dominantMakerOf(res)` (shared with §5.5's funnel) establishes the maker from the *resolved* (already-finished) tokens only.
- `filterCarsByTerms(termForms, yf)` re-scans `ALL_CARS` using just those resolved tokens — a second `O(48k)` pass, same order of cost as the main filter loop, only triggered on the mid-word condition (not every keystroke).
- `pickModelCompletion(scoped, pool, rawPartialToken)` tallies distinct model-name words (same split as `relevanceScore`'s `modelWords`) starting with the partial token, drops noise via `significantEntries`, and validates each candidate the same way the funnel does (`0 < countAfterTerm(pool, candidate) < pool.length`) before suggesting it — never a bare guess.
- **Priority: mid-word completion wins.** If it fires, both the zero-result maker-hint ghost and the append-style funnel are skipped for that keystroke — you can't sensibly append a whole new word onto one that isn't finished yet.
- Verified no perf regression even on large-catalog makers (28-58ms band, measured the same way as §4.5.1's bug) and zero effect on `autocomplete-tests/` metrics (that suite reads `#acDrop` results only, never the ghost overlay).

**Old below-list refine chips are hidden:** the `+ label count` chip row (`getRefineSuggestions` / `applyRefineChip`, shown under the dropdown when `res.length > 20`) is now `display: none` via CSS — the inline ghost covers the same purpose. The generation code is untouched (dead weight, not deleted).

**Direct ktype/car-ID lookup removed:** a purely-numeric query (`^#?(\d+)$`) used to short-circuit into a direct `car_id` lookup instead of the normal search. That branch was removed — numeric input now goes through the standard token/year pipeline like any other query.

**Zero-results maker completion:** the no-results branch already guessed a likely maker from the first 3+ typed chars (`makerHint`, e.g. `"vol"` → `"VOLVO"`) to render `Try just "VOLVO"...`. That guess is now also offered as a ghost via `updateGhostCompletion(dropId, inputId, fullText)` — it completes the **current word** (no leading space, no `+` marker, just a grey tail glued onto what's typed) rather than appending a new token like the staged-funnel ghost does. Casing of the suggested tail is normalized to match how the user is typing, since `MAKERS` names are stored upper-case and a naive slice would otherwise render e.g. `volVO`.

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
| `.ac-refine` (below-list "+ label count" chips) | CSS-hidden (`display:none`) since 2026-07, superseded by inline ghost-text (§5.5). **2026-07-21:** the `getRefineSuggestions()` call itself is now also skipped (`if (false && ...)` in `runAc`) — not just CSS-hidden — after it was found to take ~2.5s on a large unconstrained `res` (see §4.5.1). `applyRefineChip` and the function bodies are untouched, just unreachable. |

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
