#!/usr/bin/env python3
"""
Generate a deterministic set of synthetic, "realistic user" search queries
from cars_data.json, each with a known ground-truth car_id.

Usage:
    python3 generate_queries.py [--cars-per-maker N] [--seed N] [--out FILE]

Re-running with the same --seed and --cars-per-maker reproduces the exact
same query set (needed so metrics are comparable run over run). Regenerate
deliberately (e.g. after cars_data.json changes materially) and note it in
the report meta.
"""
import argparse
import json
import random
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
CARS_DATA = ROOT / "cars_data.json"

TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def strip_trailing_paren(s: str) -> str:
    return TRAILING_PAREN_RE.sub("", s).strip()


def deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def make_typo(word: str, rng: random.Random) -> str:
    """Deterministic-per-call single-letter-swap typo, e.g. HYUNDAI -> HYUANDI."""
    if len(word) < 4:
        return word
    i = rng.randint(1, len(word) - 2)
    chars = list(word)
    chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return "".join(chars)


def build_variants(make: str, model: str, trim: str, fuel: str, year_from, rng: random.Random):
    """Return list of (variant_name, query_text) for one car record."""
    clean_model = strip_trailing_paren(str(model))
    trim = strip_trailing_paren(str(trim)).strip()
    variants = []

    variants.append(("make_model", f"{make} {clean_model}".strip()))
    if trim:
        variants.append(("make_model_trim", f"{make} {clean_model} {trim}".strip()))
        variants.append(("model_trim_no_make", f"{clean_model} {trim}".strip()))
    else:
        variants.append(("model_only_no_make", clean_model))

    typo = make_typo(make, rng)
    if typo != make:
        variants.append(("make_typo", f"{typo} {clean_model}".strip()))

    if year_from:
        variants.append(("make_model_year", f"{make} {clean_model} {year_from}".strip()))

    ascii_q = deaccent(f"{make} {clean_model} {trim}").lower().strip()
    variants.append(("ascii_lowercase_no_diacritics", ascii_q))

    # de-dup while preserving order (short models can make several variants identical)
    seen = set()
    out = []
    for name, text in variants:
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append((name, text))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cars-per-maker", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(Path(__file__).parent / "test_queries.json"))
    args = ap.parse_args()

    rng = random.Random(args.seed)

    with open(CARS_DATA, encoding="utf-8") as f:
        data = json.load(f)
    makers = {m["id"]: m["n"] for m in data["makers"]}

    by_maker = {}
    for c in data["cars"]:
        by_maker.setdefault(c[0], []).append(c)

    queries = []
    qid = 0
    for maker_id in sorted(by_maker):
        make_name = makers.get(maker_id, "?")
        cars = by_maker[maker_id]
        sample = rng.sample(cars, k=min(args.cars_per_maker, len(cars)))
        for c in sample:
            _, model_id, model_name, car_id, trim, fuel, year_from, year_to, kw, hp = c[:10]
            label = f"{make_name} {strip_trailing_paren(str(model_name))} {trim}".strip()
            for variant, text in build_variants(make_name, model_name, trim, fuel, year_from, rng):
                qid += 1
                queries.append({
                    "id": qid,
                    "query": text,
                    "variant": variant,
                    "expected_car_id": car_id,
                    "expected_label": label,
                    "make": make_name,
                })

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "cars_per_maker": args.cars_per_maker,
            "total_makers": len(by_maker),
            "total_cars_in_dataset": len(data["cars"]),
            "total_queries": len(queries),
        },
        "queries": queries,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(queries)} queries ({len(by_maker)} makers x up to {args.cars_per_maker} cars) -> {out_path}")


if __name__ == "__main__":
    main()
