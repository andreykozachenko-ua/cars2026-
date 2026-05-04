# Autocomplete car search — Technical Specification

## Overview
A search input with autocomplete dropdown for vehicle selection. The user types a query (make, model, year, trim) and sees matching suggestions. Selecting a result auto-fills the 4 cascading dropdowns (Make → Year → Model → Engine/Trim).

---

## Data source
JSON file `cars_data.json` with the following structure:
```json
{
  "makers": [{ "id": 3854, "n": "BMW" }],
  "cars": [
    [
      3854,         // [0] maker id
      44049,        // [1] model id
      "3er (E46)",  // [2] model name
      152402,       // [3] car id
      "320i",       // [4] car name / trim
      "Petrol",     // [5] fuel type
      1998,         // [6] year from
      2005,         // [7] year to (null = still in production)
      105,          // [8] power kW
      143           // [9] power hp
    ]
  ]
}
```
~48 000 records, ~3.6 MB. Loaded once on page init via `fetch()`.

---

## Search behaviour

**Input parsing — year detection:**
Split query by spaces. Any token matching `/^(19|20)\d{2}$/` is treated as a **year filter**, the rest as **text terms**.

Examples:
- `"bmw 3er"` → text: `["bmw", "3er"]`, year: `null`
- `"2005 volvo s40"` → text: `["volvo", "s40"]`, year: `2005`
- `"ford ranger 2006"` → text: `["ford", "ranger"]`, year: `2006`

**Filtering logic:**
```
for each car record:
  if yearFilter:
    skip if car.yearFrom > yearFilter
    skip if car.yearTo !== null && car.yearTo < yearFilter
  if textTerms.length > 0:
    haystack = maker.name + " " + car.modelName + " " + car.trimName + " " + car.fuel
    skip if NOT every term is found in haystack (case-insensitive)
  → include in results
```

**Performance:**
- Debounce input: **150ms**
- Stop collecting after **20 matches** (show 20, indicate if more exist)
- Minimum query length: **2 characters** (or 4-digit year alone)

---

## Dropdown UI

Each suggestion item shows:
```
[Make] [ModelName] · [TrimName]          ← main line, matched terms highlighted
[YearFrom–YearTo] · [Fuel] · [kW / hp]  ← subtitle line
```
If year was in query → highlight the year in subtitle in accent color.

States:
- **No results** → show "No vehicles found" message
- **>20 results** → show "Refine your search for more results" footer row
- **Loading** → spinner (shown while `cars_data.json` is fetching)

Keyboard navigation: `↑` `↓` to move focus, `Enter` to select, `Escape` to close.

---

## Auto-fill on select

When user picks a suggestion, the 4 dropdowns fill sequentially:

1. Set **Make** dropdown → trigger `change` event
2. Wait (async) → set **Year** dropdown:
   - Prefer the year from search query if present
   - Otherwise use `car.yearFrom`
   - If exact year not in list → pick closest year within production range
3. Wait → set **Model** dropdown → trigger `change`
4. Wait → set **Engine/Trim** dropdown → trigger `change`

Each `change` event cascades filtering to the next dropdown.

---

## Clear button
`×` button inside the input field, visible only when input has value. Clears input, closes dropdown, resets focus.

---

## Notes for integration
- The search works **independently** from the step-by-step dropdowns — both can be used to reach the same result
- No backend required — all filtering happens client-side
- The same `cars_data.json` is shared between search and dropdowns
