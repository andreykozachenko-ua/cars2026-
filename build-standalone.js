#!/usr/bin/env node
// Generates index-noplate-standalone.html — works via file:// without a local server.
// Usage: node build-standalone.js

const fs = require('fs');
const path = require('path');

const dir = __dirname;
const src = path.join(dir, 'index-noplate.html');
const out = path.join(dir, 'index-noplate-standalone.html');

console.log('Reading data files…');
const carsData    = fs.readFileSync(path.join(dir, 'cars_data.json'),    'utf8');
const modelGroups = fs.readFileSync(path.join(dir, 'model_groups.json'), 'utf8');
const bmwCsv      = fs.readFileSync(path.join(dir, 'bmw.csv'),           'utf8');

// Inline data block — injected before </body>
const inlineScript = `<script>
window.__INLINE_CARS_DATA    = ${carsData};
window.__INLINE_MODEL_GROUPS = ${modelGroups};
window.__INLINE_BMW_CSV      = ${JSON.stringify(bmwCsv)};
</script>`;

// Replace the fetch() Promise.all block with an inline-data loader
// that falls back to fetch() if inline globals are absent (server mode).
const fetchBlock = `Promise.all([
  fetch('cars_data.json').then(r => r.json()),
  fetch('bmw.csv').then(r => r.text()).catch(() => ''),
  fetch('model_groups.json').then(r => r.json()).catch(() => ({}))
]).then(([data, csv, groups]) => {
  MAKERS = data.makers; ALL_CARS = data.cars; MODEL_GROUPS = groups;
  if (csv) parseRatingsCsv(csv);
  resetFindBtn(); renderMakerShortcuts();
}).catch(() => { document.getElementById('findBtn').textContent = 'Failed to load — use a local server'; });`;

const inlineLoader = `(function() {
  var data   = window.__INLINE_CARS_DATA    || null;
  var groups = window.__INLINE_MODEL_GROUPS || null;
  var csv    = window.__INLINE_BMW_CSV      || '';
  if (data && groups) {
    MAKERS = data.makers; ALL_CARS = data.cars; MODEL_GROUPS = groups;
    if (csv) parseRatingsCsv(csv);
    resetFindBtn(); renderMakerShortcuts();
  } else {
    Promise.all([
      fetch('cars_data.json').then(r => r.json()),
      fetch('bmw.csv').then(r => r.text()).catch(() => ''),
      fetch('model_groups.json').then(r => r.json()).catch(() => ({}))
    ]).then(([data, csv, groups]) => {
      MAKERS = data.makers; ALL_CARS = data.cars; MODEL_GROUPS = groups;
      if (csv) parseRatingsCsv(csv);
      resetFindBtn(); renderMakerShortcuts();
    }).catch(() => { document.getElementById('findBtn').textContent = 'Failed to load — use a local server'; });
  }
})();`;

console.log('Patching HTML…');
let html = fs.readFileSync(src, 'utf8');

if (!html.includes(fetchBlock.trim().slice(0, 40))) {
  console.error('ERROR: fetch block not found in source — check index-noplate.html for changes.');
  process.exit(1);
}

html = html.replace(fetchBlock, inlineLoader);
html = html.replace('</body>', inlineScript + '\n</body>');

fs.writeFileSync(out, html, 'utf8');
const sizeMB = (fs.statSync(out).size / 1024 / 1024).toFixed(1);
console.log(`Done → index-noplate-standalone.html (${sizeMB} MB)`);
console.log('Open in browser: open index-noplate-standalone.html');
