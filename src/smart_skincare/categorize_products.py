"""
Categorize products by keyword matching on product names.

Reads cosmetics.csv and Sephora_all_423.csv, assigns a category to each product
based on keywords found in the product name. Priority-ordered so "Eye Cream"
maps to Eye Care (not Moisturizer), "Exfoliating Toner" maps to Exfoliator, etc.

Usage: python categorize_products.py
"""
import csv
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"

# ── Category definitions (checked in priority order) ──────────────────────
# Each entry: (category_name, keywords, exclude_keywords)
# First match wins, so more specific categories come first.
CATEGORY_RULES = [
    ("Lip Care",     ["lip balm", "lip mask", "lip oil", "lip butter",
                      "lip sleep", "lip glow", "lip treat", "lip gloss",
                      "lip liner", "lip stick", "lipstick"],            []),
    ("Eye Care",     ["eye cream", "eye serum", "eye gel", "eye mask",
                      "eye treatment", "eye oil", "eye contour",
                      "undereye", "under-eye", "under eye",
                      "eye patch", "eye patch"],                        []),
    ("Sunscreen",    ["sunscreen", "sun protect", "spf"],               ["after sun"]),
    ("Cleanser",     ["cleanser", "cleansing", "face wash",
                      "facial wash", "foaming wash", "cleansing gel",
                      "cleansing foam", "cleansing oil",
                      "cleansing water", "micellar",
                      "makeup remover", "rice polish", "powder wash"],  []),
    ("Exfoliator",   ["exfoliat", "scrub", "peel", "peeling"],          []),
    ("Mask",         ["mask", "masque"],                                []),
    ("Toner",        ["toner", "toning", "tonique"],                    []),
    ("Serum",        ["serum", "ampoule", "ampule", "concentrate",
                      "drops"],                                         []),
    ("Essence",      ["essence"],                                       []),
    ("Moisturizer",  ["moisturizer", "moisturiser", "cream", "crème", "creme",
                      "lotion", "hydrator", "emulsion", "sorbet",
                      "moisturizing gel", "gel-cream", "gel cream",
                      "hydrating jelly", "jelly", "softener",
                      "moisture", "hydrating gel", "water gel",
                      "gel oil-free", "cushion"],                       []),
    ("Facial Oil",   ["facial oil", "face oil", "night oil",
                      "sleep oil", "skin oil", "beauty oil",
                      " oil"],                                          ["oil-free", "oil free",
                                                                         "cleansing oil"]),
    ("Mist",         ["mist", "spray", "facial spray"],                 []),
    ("Balm",         ["balm"],                                          []),
    ("Treatment",    ["treatment", "retinol", "acne", "repair",
                      "recovery", "corrector"],                         []),
    ("Primer",       ["primer"],                                        []),
    ("Set/Kit",      ["set", "kit", "trio", "duo", "the littles",
                      "collection", "bundle", "mini"],                  []),
]


def _match_keywords(text: str) -> str | None:
    """Try matching text against CATEGORY_RULES. Return category or None."""
    if not text:
        return None
    low = " " + text.strip().lower() + " "
    for category, keywords, excludes in CATEGORY_RULES:
        if any(ex in low for ex in excludes):
            continue
        if any(kw in low for kw in keywords):
            return category
    return None


# cosmetics.csv Label → our category mapping
LABEL_MAP = {
    "moisturizer": "Moisturizer",
    "cleanser": "Cleanser",
    "face mask": "Mask",
    "treatment": "Treatment",
    "eye cream": "Eye Care",
    "sun protect": "Sunscreen",
}


def categorize(name: str, description: str = "", original_label: str = "") -> str:
    """Return category for a product. Tries name first, then description, then label."""
    # 1) keyword match on product name
    cat = _match_keywords(name)
    if cat:
        return cat

    # 2) keyword match on product description (Sephora 'What it is')
    cat = _match_keywords(description)
    if cat:
        return cat

    # 3) fall back to cosmetics.csv Label column
    if original_label:
        mapped = LABEL_MAP.get(original_label.strip().lower())
        if mapped:
            return mapped

    return "Other"


def load_products() -> list[dict]:
    """Load products from both CSVs with unified fields."""
    products = []

    # cosmetics.csv
    path_c = DATA_DIR / "cosmetics.csv"
    if path_c.exists():
        with open(path_c, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                products.append({
                    "source": "cosmetics",
                    "brand": (row.get("Brand") or "").strip(),
                    "name": (row.get("Name") or "").strip(),
                    "description": "",
                    "original_label": (row.get("Label") or "").strip(),
                })

    # Sephora_all_423.csv
    path_s = DATA_DIR / "Sephora_all_423.csv"
    if path_s.exists():
        with open(path_s, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                products.append({
                    "source": "sephora",
                    "brand": (row.get("brand_name") or "").strip(),
                    "name": (row.get("cosmetic_name") or "").strip(),
                    "description": (row.get("What it is") or "").strip(),
                    "original_label": "",
                })

    return products


def main():
    products = load_products()
    print(f"Total products loaded: {len(products)}")
    print()

    # Assign categories
    for p in products:
        p["category"] = categorize(p["name"], p["description"], p["original_label"])

    # Summary
    counter = Counter(p["category"] for p in products)
    print(f"{'Category':<16} {'Count':>6}  {'%':>6}")
    print("-" * 32)
    for cat, cnt in counter.most_common():
        print(f"{cat:<16} {cnt:>6}  {cnt/len(products)*100:>5.1f}%")

    # Other examples (for tuning)
    others = [p for p in products if p["category"] == "Other"]
    if others:
        print(f"\n── 'Other' sample (up to 20) ──")
        for p in others[:20]:
            print(f"  [{p['source'][:4]}] {p['brand']} — {p['name']}")


if __name__ == "__main__":
    main()
