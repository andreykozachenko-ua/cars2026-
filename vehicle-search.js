/**
 * VehicleSearch — standalone vehicle autocomplete engine
 * No dependencies. Works in browser (window.VehicleSearch) and Node.js (module.exports).
 *
 * Usage:
 *   VehicleSearch.load(data);          // once, after fetching JSON
 *   VehicleSearch.search('bmw 320d');  // returns array of result objects
 */
(function (global) {
  'use strict';

  // ── Synonym groups ───────────────────────────────────────────────────────────
  // Each group: any term in the query expands to ALL terms in its group (OR match).
  var SYNONYM_GROUPS = [
    ['vw', 'volkswagen'],
    ['mk1','i'], ['mk2','ii'], ['mk3','iii'], ['mk4','iv'],
    ['mk5','v'], ['mk6','vi'], ['mk7','vii'], ['mk8','viii'],
    ['estate','variant','touring','avant','sw','kombi','break','wagon','sports tourer','sport tourer'],
    ['cabriolet','cabrio','convertible','roadster','spider','spyder','open','drop'],
    ['coupe', 'coupé', 'coupe'],
    ['saloon', 'sedan', 'berline', 'limousine', 'limo'],
    ['suv', 'crossover', 'offroad', 'off-road'],
    ['van', 'minivan', 'mpv', 'people carrier'],
    ['pickup', 'pick-up', 'truck'],
    ['4motion','quattro','xdrive','awd','4wd','4x4','syncro','allrad','terradrive','terracan'],
    ['diesel','tdi','tdi','dci','hdi','cdti','cdi','jtd','d4d','tdci','sdi','crdi','ddis','dti'],
    ['petrol','tsi','tfsi','fsi','gti','gsi','vtec','cvvt','mpi','gdi','cgi'],
    ['hybrid','hev','phev','mhev','fhev'],
    ['electric','ev','bev','e-tron','ioniq'],
    ['lpg','autogas'],
    ['auto','automatic','dsg','tiptronic','s-tronic','cvt','multitronic','pdk','steptronic','powershift'],
    ['manual','mt','gearbox'],
  ];

  // ── Number ↔ Roman numeral synonyms ─────────────────────────────────────────
  var NUM2ROM = { '1':'i','2':'ii','3':'iii','4':'iv','5':'v','6':'vi','7':'vii','8':'viii','9':'ix','10':'x' };
  var ROM2NUM = {};
  Object.keys(NUM2ROM).forEach(function(k) { ROM2NUM[NUM2ROM[k]] = k; });

  // ── Pre-compile synonym structures at module init (not per-search) ───────────
  var SYNONYM_MAP = new Map();   // word → group array
  var SYNONYM_RE  = new Map();   // word → pre-compiled RegExp

  SYNONYM_GROUPS.forEach(function(g) {
    g.forEach(function(w) {
      SYNONYM_MAP.set(w, g);
      SYNONYM_RE.set(w, new RegExp('(?:^|\\s)' + escRe(w) + '(?=\\s|$)'));
    });
  });

  // Pre-compile roman ↔ number regexes
  Object.keys(NUM2ROM).forEach(function(n) {
    var r = NUM2ROM[n];
    if (!SYNONYM_RE.has(n)) SYNONYM_RE.set(n, new RegExp('(?:^|\\s)' + escRe(n) + '(?=\\s|$)'));
    if (!SYNONYM_RE.has(r)) SYNONYM_RE.set(r, new RegExp('(?:^|\\s)' + escRe(r) + '(?=\\s|$)'));
  });

  // ── Utilities ────────────────────────────────────────────────────────────────
  function deaccent(s) {
    return s.normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function escRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function termMatchers(t) {
    // Synonym group expansion
    var group = SYNONYM_MAP.get(t);
    if (group) {
      return group.map(function(f) { return { str: f, re: SYNONYM_RE.get(f) || null }; });
    }
    // Roman ↔ number
    var alt = NUM2ROM[t] || ROM2NUM[t];
    if (alt) {
      return [
        { str: t,   re: SYNONYM_RE.get(t)   || null },
        { str: alt, re: SYNONYM_RE.get(alt) || null },
      ];
    }
    // Literal
    return [{ str: t, re: null }];
  }

  // Pre-compute haystack string for one car (called once at load, not per search)
  // driveType / bodyType are canonical text tokens from TecDoc KT 082 / KT 086,
  // e.g. driveType="awd", bodyType="estate" — matched via existing SYNONYM_GROUPS
  function buildHay(makeName, modelName, trimName, fuel, driveType, bodyType) {
    var base = deaccent([makeName, modelName, trimName, fuel||'', driveType||'', bodyType||''].join(' ')).toLowerCase();
    var n1 = base.replace(/[-()_\/]/g, ' ');                        // dashes → spaces
    var n2 = base.replace(/[()_\/]/g, ' ').replace(/-/g, '');       // dashes removed
    var n3 = n1.replace(/\b([a-z]) (\d+)\b/g, '$1$2');              // "e 320" → "e320"
    return n1 + ' ' + n2 + ' ' + n3;
  }

  // ── Engine state ─────────────────────────────────────────────────────────────
  var _cars    = [];
  var _ratings = new Map();
  var _ready   = false;

  // ── Public API ───────────────────────────────────────────────────────────────
  var VehicleSearch = {

    /**
     * Load and pre-process the vehicle index.
     *
     * @param {Object} data     Parsed JSON: { makers: [[id, name], ...], cars: [[...], ...] }
     *
     * Car array columns (positional):
     *   [0] makeId    INT    — foreign key into makers
     *   [1] modelId   INT    — model group identifier
     *   [2] modelName STRING — "3 Series", "Golf"
     *   [3] carId     INT    — unique engine/trim identifier (TecDoc carId)
     *   [4] trimName  STRING — "320d xDrive Touring"
     *   [5] fuel      STRING — "Diesel", "Petrol", "Petrol/Electric", ...
     *   [6] yearFrom  INT    — production start year
     *   [7] yearTo    INT|null — production end year (null = current)
     *   [8] kw        INT|null — engine power in kilowatts
     *   [9] hp        INT|null — engine power in horsepower
     *  [10] driveType STRING|null — canonical drive type token from TecDoc KT 082
     *                               use lowercase: "awd", "rwd", "fwd"
     *                               matched via SYNONYM_GROUPS: "awd"↔"quattro"↔"xdrive"↔"4x4"
     *  [11] bodyType  STRING|null — canonical body type token from TecDoc KT 086
     *                               use lowercase: "estate", "saloon", "suv", "coupe", "cabriolet"
     *                               matched via SYNONYM_GROUPS: "estate"↔"touring"↔"avant"↔"wagon"
     *
     * @param {Object} [ratings]  Optional map { carId: score } for popularity ranking.
     *                            Higher score = appears first in results.
     * @returns {VehicleSearch}   Chainable.
     */
    load: function(data, ratings) {
      var makersMap = new Map();
      (data.makers || []).forEach(function(m) { makersMap.set(m[0], m[1]); });

      _ratings = new Map();
      if (ratings) {
        Object.keys(ratings).forEach(function(k) { _ratings.set(+k, ratings[k]); });
      }

      _cars = (data.cars || []).map(function(c) {
        var makeName = makersMap.get(c[0]) || '';
        return {
          makeId:    c[0],
          modelId:   c[1],
          modelName: c[2],
          carId:     c[3],
          trimName:  c[4],
          fuel:      c[5] || '',
          yearFrom:  c[6],
          yearTo:    c[7],
          kw:        c[8],
          hp:        c[9],
          make:      makeName,
          driveType: c[10] || '',
          bodyType:  c[11] || '',
          _hay:      buildHay(makeName, c[2] || '', c[4] || '', c[5] || '', c[10] || '', c[11] || ''),
        };
      });

      _ready = true;
      return this;
    },

    /**
     * Search the loaded index.
     *
     * @param {string} query   Raw user input, any language, any case.
     * @param {number} [limit] Max results to return. Default 8.
     * @returns {Array}        Array of result objects (see below), sorted by popularity.
     *
     * Result object:
     *   { carId, makeId, make, model, trim, fuel, yearFrom, yearTo, kw, hp }
     */
    search: function(query, limit) {
      if (!_ready || !query || query.length < 2) return [];
      limit = limit || 8;

      // Normalise query
      var norm = deaccent(query)
        .toLowerCase()
        .replace(/[-()_\/]/g, ' ')
        .replace(/([a-zA-Z]{3,})(\d)/g, '$1 $2')   // "golf5"  → "golf 5"
        .replace(/(\d)([a-zA-Z]{2,})/g, '$1 $2')   // "320d"   → "320 d"
        .split(/\s+/)
        .filter(Boolean);

      var yf = null;
      var terms = [];
      norm.forEach(function(p) {
        if (/^(19|20)\d{2}$/.test(p)) { yf = +p; } else { terms.push(p); }
      });

      var termForms = terms.map(termMatchers);
      var results = [];

      for (var i = 0; i < _cars.length; i++) {
        var c = _cars[i];

        // Year filter
        if (yf !== null) {
          if (c.yearFrom > yf) continue;
          if (c.yearTo !== null && c.yearTo < yf) continue;
        }

        // Term matching: ALL terms must match (AND), each term via ANY synonym (OR)
        if (termForms.length) {
          var hay = c._hay;
          var allMatch = true;
          for (var t = 0; t < termForms.length; t++) {
            var forms = termForms[t];
            var anyMatch = false;
            for (var f = 0; f < forms.length; f++) {
              var form = forms[f];
              if (form.re ? form.re.test(hay) : hay.indexOf(form.str) !== -1) {
                anyMatch = true;
                break;
              }
            }
            if (!anyMatch) { allMatch = false; break; }
          }
          if (!allMatch) continue;
        }

        results.push(c);
      }

      // Sort by popularity score descending
      results.sort(function(a, b) {
        return (_ratings.get(b.carId) || 0) - (_ratings.get(a.carId) || 0);
      });

      return results.slice(0, limit).map(function(c) {
        return {
          carId:    c.carId,
          makeId:   c.makeId,
          make:     c.make,
          model:    c.modelName,
          trim:     c.trimName,
          fuel:     c.fuel,
          yearFrom: c.yearFrom,
          yearTo:   c.yearTo,
          kw:       c.kw,
          hp:       c.hp,
        };
      });
    },

    /**
     * Highlight matched terms in a string for display.
     *
     * @param {string} text    The string to highlight (already HTML-escaped recommended).
     * @param {string} query   Same query passed to search().
     * @param {string} [tag]   Wrapper tag. Default "mark".
     * @returns {string}       String with matched terms wrapped in <tag>.
     */
    highlight: function(text, query, tag) {
      tag = tag || 'mark';
      var norm = deaccent(query).toLowerCase()
        .replace(/[-()_\/]/g, ' ')
        .replace(/([a-zA-Z]{3,})(\d)/g, '$1 $2')
        .split(/\s+/).filter(Boolean)
        .filter(function(p) { return !/^(19|20)\d{2}$/.test(p); });

      var out = text;
      norm.forEach(function(t) {
        try {
          out = out.replace(
            new RegExp('(' + escRe(t) + ')', 'gi'),
            '<' + tag + '>$1</' + tag + '>'
          );
        } catch(e) {}
      });
      return out;
    },

    /** Returns true after load() has been called successfully. */
    isReady: function() { return _ready; },

    /** Total number of loaded car configurations. */
    size: function() { return _cars.length; },
  };

  // ── Export ───────────────────────────────────────────────────────────────────
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = VehicleSearch;
  } else {
    global.VehicleSearch = VehicleSearch;
  }

}(typeof window !== 'undefined' ? window : this));
