"""List products with empty ingredients; print raw + tag so we can see why empty.
  --all: show all with empty parsed ingredients (default)
  --csv-only: show only those where CSV had no ingredients (raw was empty)
"""
import argparse
import re

from recommend_mvp import load_products_with_ingredients


def safe_print(s):
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", errors="replace").decode("ascii"))

def _infer_empty_hint(raw: str) -> str:
    """Infer why parsed ingredients might be empty (for parsed_empty cases)."""
    if not raw:
        return "raw_empty"
    low = raw.strip().lower()
    if any(x in low for x in ("ingredient list is subject to change", "take the quiz", "to view your formulations", "may differ from packaging", "skin genome quiz")):
        return "disclaimer/quiz"
    if any(x in low for x in ("based on quiz", "ingredients will be based", "your formulations", "personalized")):
        return "dynamic_formula"
    if any(x in low for x in ("pillowcase", "silk", "momme", "thread count", "mulberry silk")):
        return "material"
    if "%" in raw and re.search(r"\d+\s*%", raw):
        return "possible_percent_dropped"
    if raw.count(",") < 2 and len(raw) > 50:
        return "possible_marketing_bullet"
    return "parsed_empty"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-only", action="store_true", help="Only products where CSV ingredients column was empty")
    ap.add_argument("--all", action="store_true", help="All with empty parsed ingredients (default)")
    args = ap.parse_args()
    csv_only = args.csv_only

    products = load_products_with_ingredients(max_products=None)
    empty = [p for p in products if not (p.get("ingredients") or [])]
    if csv_only:
        empty = [p for p in empty if not (p.get("raw_ingredients") or "").strip()]
        print("Products where CSV ingredients column was empty:", len(empty))
    else:
        print("Total with empty ingredients (parsed):", len(empty))
    print()
    for i, p in enumerate(empty, 1):
        src = p.get("source", "?")
        brand = p.get("brand", "")
        name = (p.get("name", ""))[:60]
        raw = (p.get("raw_ingredients") or "").strip()
        tag = p.get("no_ingredients_reason") or _infer_empty_hint(raw)
        safe_print(f"{i}. [{src}] {brand} | {name}")
        safe_print(f"   tag={tag}")
        safe_print(f"   raw={raw[:200]}{'...' if len(raw) > 200 else ''}")
        safe_print("")

if __name__ == "__main__":
    main()
