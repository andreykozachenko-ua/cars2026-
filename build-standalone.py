#!/usr/bin/env python3
# Generates index-noplate-standalone.html — works via file:// without a local server.
# Usage: python3 build-standalone.py

import json, os, sys

DIR = os.path.dirname(os.path.abspath(__file__))

def read(name):
    with open(os.path.join(DIR, name), encoding='utf-8') as f:
        return f.read()

print('Reading data files…')
cars_raw   = read('cars_data.json')
groups_raw = read('model_groups.json')
csv_raw    = read('bmw.csv')

inline_script = f"""<script>
window.__INLINE_CARS_DATA    = {cars_raw};
window.__INLINE_MODEL_GROUPS = {groups_raw};
window.__INLINE_BMW_CSV      = {json.dumps(csv_raw)};
</script>"""

FETCH_BLOCK = """Promise.all([
  fetch('cars_data.json').then(r => r.json()),
  fetch('bmw.csv').then(r => r.text()).catch(() => ''),
  fetch('model_groups.json').then(r => r.json()).catch(() => ({}))
]).then(([data, csv, groups]) => {
  MAKERS = data.makers; ALL_CARS = data.cars; MODEL_GROUPS = groups;
  MAKERS_MAP = new Map(MAKERS.map(m => [m.id, m.n]));
  ALL_CARS.forEach(c => { c._hay = buildHay(MAKERS_MAP.get(c[0])||'', c[2], c[4], normalizeFuel(c[5]), c[10], c[11]); });
  if (csv) parseRatingsCsv(csv);
  resetFindBtn(); renderMakerShortcuts();
}).catch(() => { document.getElementById('findBtn').textContent = 'Failed to load — use a local server'; });"""

INLINE_LOADER = """(function() {
  var data   = window.__INLINE_CARS_DATA    || null;
  var groups = window.__INLINE_MODEL_GROUPS || null;
  var csv    = window.__INLINE_BMW_CSV      || '';
  if (data && groups) {
    MAKERS = data.makers; ALL_CARS = data.cars; MODEL_GROUPS = groups;
    MAKERS_MAP = new Map(MAKERS.map(m => [m.id, m.n]));
    ALL_CARS.forEach(c => { c._hay = buildHay(MAKERS_MAP.get(c[0])||'', c[2], c[4], normalizeFuel(c[5]), c[10], c[11]); });
    if (csv) parseRatingsCsv(csv);
    resetFindBtn(); renderMakerShortcuts();
  } else {
    Promise.all([
      fetch('cars_data.json').then(r => r.json()),
      fetch('bmw.csv').then(r => r.text()).catch(() => ''),
      fetch('model_groups.json').then(r => r.json()).catch(() => ({}))
    ]).then(([data, csv, groups]) => {
      MAKERS = data.makers; ALL_CARS = data.cars; MODEL_GROUPS = groups;
      MAKERS_MAP = new Map(MAKERS.map(m => [m.id, m.n]));
      ALL_CARS.forEach(c => { c._hay = buildHay(MAKERS_MAP.get(c[0])||'', c[2], c[4], normalizeFuel(c[5]), c[10], c[11]); });
      if (csv) parseRatingsCsv(csv);
      resetFindBtn(); renderMakerShortcuts();
    }).catch(() => { document.getElementById('findBtn').textContent = 'Failed to load'; });
  }
})();"""

print('Patching HTML…')
html = read('index-noplate.html')

if FETCH_BLOCK not in html:
    print('ERROR: fetch block not found in index-noplate.html — source may have changed.')
    sys.exit(1)

DEBUG_PANEL = """<div id="__dbg" style="position:fixed;bottom:0;left:0;right:0;background:#111;color:#0f0;font:12px monospace;padding:8px 12px;z-index:9999;max-height:120px;overflow:auto"></div>
<script>
window.onerror = function(msg, src, line, col, err) {
  var d = document.getElementById('__dbg');
  if (d) d.innerHTML += '<br>ERROR ' + line + ': ' + msg;
};
window.__dbg = function(msg) {
  var d = document.getElementById('__dbg');
  if (d) d.innerHTML += msg + '<br>';
};
</script>"""

html = html.replace(FETCH_BLOCK, INLINE_LOADER)
# Inject data BEFORE the main <script> block so globals are set before the loader runs
html = html.replace('<script>', inline_script + '\n<script>', 1)
# Inject debug panel right after <body>
html = html.replace('<body>', '<body>' + DEBUG_PANEL, 1)
# Add debug checkpoint after inline loader
html = html.replace(
    'resetFindBtn(); renderMakerShortcuts();\n  } else {',
    'resetFindBtn(); renderMakerShortcuts(); window.__dbg("OK: cars=" + ALL_CARS.length + " makers=" + MAKERS.length);\n  } else {'
)

out = os.path.join(DIR, 'index-noplate-standalone.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

size_mb = os.path.getsize(out) / 1024 / 1024
print(f'Done → index-noplate-standalone.html ({size_mb:.1f} MB)')
print(f'Open:  open "{out}"')
