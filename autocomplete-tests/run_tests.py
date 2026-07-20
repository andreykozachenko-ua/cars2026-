#!/usr/bin/env python3
"""
Drive index-noplate.html's real search box in a headless browser for every
query in test_queries.json, record where (if at all) the expected car_id
shows up in the rendered #acDrop dropdown, and report aggregate metrics.

This exercises the actual production code path: input -> 'input' event ->
app's own debounce -> runAc() -> DOM render. It does NOT simulate individual
keystrokes or the ghost-text accept/dismiss flow (Tab/Escape/arrow keys) -
those are input-UX affordances, not the search-relevance logic this metric
targets. Add a separate keystroke-level test if ghost-text itself needs
regression coverage.

Usage:
    python3 run_tests.py [--queries FILE] [--port 8899] [--limit N] [--headed]
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent  # cars_privat/
TESTS_DIR = Path(__file__).resolve().parent
ONCLICK_CARID_RE = re.compile(r"pickAc\((\d+)\)")


def start_server(port: int):
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        time.sleep(0.1)
        if proc.poll() is not None:
            raise RuntimeError("local http.server failed to start")
    time.sleep(0.3)
    return proc


def run(queries_path: Path, port: int, limit: int, headed: bool):
    data = json.loads(queries_path.read_text(encoding="utf-8"))
    queries = data["queries"]
    if limit:
        queries = queries[:limit]

    server = start_server(port)
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            page = browser.new_page()
            page.goto(f"http://localhost:{port}/index-noplate.html")
            page.wait_for_function("() => typeof ALL_CARS !== 'undefined' && ALL_CARS.length > 0", timeout=20000)

            for i, q in enumerate(queries, 1):
                page.fill("#searchInput", "")
                page.fill("#searchInput", q["query"])
                page.wait_for_timeout(220)  # debounce is 150ms in-app

                dropdown_visible = page.eval_on_selector(
                    "#acDrop", "el => el.style.display === 'block'"
                ) or False
                onclicks = page.eval_on_selector_all(
                    "#acDrop .ac-item", "els => els.map(el => el.getAttribute('onclick'))"
                )
                returned_ids = [int(m.group(1)) for oc in onclicks if oc for m in [ONCLICK_CARID_RE.search(oc)]]

                zero_results = dropdown_visible and len(returned_ids) == 0
                rank = None
                if q["expected_car_id"] in returned_ids:
                    rank = returned_ids.index(q["expected_car_id"]) + 1

                top1_id = returned_ids[0] if returned_ids else None
                top1_label = None
                if top1_id is not None:
                    try:
                        top1_label = page.eval_on_selector("#acDrop .ac-item", "el => el.innerText")
                    except Exception:
                        pass

                results.append({
                    **{k: q[k] for k in ("id", "query", "variant", "expected_car_id", "expected_label", "make")},
                    "rank": rank,
                    "zero_results": zero_results,
                    "returned_count": len(returned_ids),
                    "top1_id": top1_id,
                    "top1_label": top1_label,
                })

                if i % 100 == 0:
                    print(f"  ...{i}/{len(queries)}", file=sys.stderr)

            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=5)

    return results


def aggregate(results):
    n = len(results)
    def pct(cond):
        return round(100 * sum(1 for r in results if cond(r)) / n, 1) if n else 0.0

    mrr = sum((1 / r["rank"]) if r["rank"] else 0.0 for r in results) / n if n else 0.0

    by_variant = {}
    for r in results:
        by_variant.setdefault(r["variant"], []).append(r)
    variant_stats = {}
    for variant, rs in by_variant.items():
        vn = len(rs)
        variant_stats[variant] = {
            "n": vn,
            "top1_pct": round(100 * sum(1 for r in rs if r["rank"] == 1) / vn, 1),
            "top5_pct": round(100 * sum(1 for r in rs if r["rank"] and r["rank"] <= 5) / vn, 1),
            "found_pct": round(100 * sum(1 for r in rs if r["rank"]) / vn, 1),
            "zero_result_pct": round(100 * sum(1 for r in rs if r["zero_results"]) / vn, 1),
            "mrr": round(sum((1 / r["rank"]) if r["rank"] else 0.0 for r in rs) / vn, 3),
        }

    return {
        "total_queries": n,
        "top1_accuracy_pct": pct(lambda r: r["rank"] == 1),
        "top5_accuracy_pct": pct(lambda r: r["rank"] is not None and r["rank"] <= 5),
        "found_in_top20_pct": pct(lambda r: r["rank"] is not None),
        "zero_result_pct": pct(lambda r: r["zero_results"]),
        "mrr": round(mrr, 3),
        "by_variant": variant_stats,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default=str(TESTS_DIR / "test_queries.json"))
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--limit", type=int, default=0, help="only run first N queries (0 = all)")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    print(f"Running autocomplete search test against index-noplate.html ...", file=sys.stderr)
    results = run(Path(args.queries), args.port, args.limit, args.headed)
    metrics = aggregate(results)

    failures = [r for r in results if r["rank"] != 1]
    failures.sort(key=lambda r: (r["rank"] is not None, r["rank"] or 999))

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "failures": failures,
    }

    reports_dir = TESTS_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = reports_dir / f"report_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = reports_dir / "latest.json"
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 60)
    print(f"AUTOCOMPLETE SEARCH METRICS  ({metrics['total_queries']} queries)")
    print("=" * 60)
    print(f"Top-1 accuracy     : {metrics['top1_accuracy_pct']}%")
    print(f"Top-5 accuracy     : {metrics['top5_accuracy_pct']}%")
    print(f"Found in top-20    : {metrics['found_in_top20_pct']}%")
    print(f"Zero-result rate   : {metrics['zero_result_pct']}%")
    print(f"MRR                : {metrics['mrr']}")
    print()
    print("By query type:")
    print(f"{'variant':<30} {'n':>5} {'top1%':>7} {'top5%':>7} {'found%':>7} {'zero%':>7} {'mrr':>6}")
    for variant, s in sorted(metrics["by_variant"].items(), key=lambda kv: kv[1]["top1_pct"]):
        print(f"{variant:<30} {s['n']:>5} {s['top1_pct']:>7} {s['top5_pct']:>7} {s['found_pct']:>7} {s['zero_result_pct']:>7} {s['mrr']:>6}")
    print()
    print(f"Full report: {out_path}")
    print(f"({len(failures)} non-top-1 queries in 'failures')")


if __name__ == "__main__":
    main()
