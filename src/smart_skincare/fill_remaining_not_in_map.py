"""
Fill ingredients that appear in products but are not yet in ingredient_skin_map.
Uses the same rule/keyword logic as fill_needs_human_withSearch.fill_row.
Output: withSearch_filled_remaining.csv. Build merges it via load_withSearch_filled_remaining().

Run after build (so we know current map). Then run build again to merge.
  python fill_remaining_not_in_map.py
  python build_ingredient_skin_map.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"
CACHE_DIR = ROOT / "cache"
INGREDIENT_SKIN_MAP_PATH = CACHE_DIR / "ingredient_skin_map.json"
WITHSEARCH_FILLED_REMAINING_PATH = DATA_DIR / "withSearch_filled_remaining.csv"


def _load_current_map_keys() -> set:
    """Current ingredient_skin_map.json keys (normalized lower)."""
    if not INGREDIENT_SKIN_MAP_PATH.exists():
        return set()
    import json
    with open(INGREDIENT_SKIN_MAP_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {k.strip().lower() for k in raw if k}


def main():
    from recommend_mvp import load_products_with_ingredients
    from fill_needs_human_withSearch import fill_row

    products = load_products_with_ingredients(max_products=None)
    products = [p for p in products if not p.get("exclude_recommendation")]

    all_ings = set()
    for p in products:
        for ing in (p.get("ingredients") or []):
            if ing and str(ing).strip():
                all_ings.add(ing.strip())

    map_keys = _load_current_map_keys()
    not_in_map = sorted([ing for ing in all_ings if ing.strip().lower() not in map_keys])

    if not not_in_map:
        print("No remaining ingredients outside map. Nothing to fill.")
        return

    rows = []
    for ing in not_in_map:
        skin_type_str, effect, confidence = fill_row(ing)
        rows.append({
            "ingredient": ing,
            "skin_type": skin_type_str,
            "effect": effect,
            "confidence": confidence,
        })

    with open(WITHSEARCH_FILLED_REMAINING_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ingredient", "skin_type", "effect", "confidence"])
        w.writeheader()
        w.writerows(rows)

    print(f"withSearch_filled_remaining.csv: {len(rows)} rows (ingredients in products, not in map)")
    print(f"Run: python build_ingredient_skin_map.py")


if __name__ == "__main__":
    main()
