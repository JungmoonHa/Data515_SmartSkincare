"""
STEP 4 — Export top 1000 unmatched ingredients to CSV for manual curation.
Columns: ingredient, source, skin_type, notes, confidence
Fill in Google Sheet; save as manual_curation.csv and run build_ingredient_skin_map.py to merge.
"""
import csv
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
DATA_DIR = ROOT / "data"
OUTPUT_CSV = DATA_DIR / "top1000_unmatched_for_curation.csv"
TOP_N = 1000


def main():
    sys.path.insert(0, str(SCRIPTS_DIR))
    from match_pipeline import (
        load_paula_ingredients,
        load_alternatives,
        load_all_unmapped_ingredients,
        load_ingredient_frequency,
        run_matching,
    )

    paula_set, _ = load_paula_ingredients(use_embedding_file=True)
    if not paula_set:
        paula_set, _ = load_paula_ingredients(use_embedding_file=False)
    _, alternatives_by_ingredient = load_alternatives()
    all_ingredients = load_all_unmapped_ingredients(use_canonical=True)
    freq = load_ingredient_frequency(use_canonical=True)

    # Run matching with INCI sample 0 so we get true unmatched (or use 200 to be fast and get "candidate" unmatched)
    _, _, _, linkable_via_alternatives, unmatched = run_matching(
        paula_set,
        all_ingredients,
        alternatives_by_ingredient,
        use_pubchem=False,
        use_incidecoder=False,
    )
    # Sort unmatched by frequency desc, take top TOP_N
    ordered = sorted(unmatched, key=lambda x: -freq.get(x, 0))[:TOP_N]

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ingredient", "source", "skin_type", "notes", "confidence"])
        for ing in ordered:
            w.writerow([ing, "", "", "", ""])

    print(f"Exported top {len(ordered)} unmatched to {OUTPUT_CSV.name}")
    print("Fill source (e.g. Paula/manual), skin_type (comma-separated: dry, oily, sensitive, pigmentation, wrinkle, normal), notes, confidence (high/medium/low).")
    print("Save as manual_curation.csv in this folder, then run build_ingredient_skin_map.py")


if __name__ == "__main__":
    main()
