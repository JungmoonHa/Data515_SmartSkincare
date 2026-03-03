"""
Pipeline step 2: Apply rule pass A–D on needs_human_filtered.csv.
- Input: needs_human_filtered.csv (from filter_needs_human.py)
- For each row: if ingredient matches CURATION_RULES (from fill_curation_rules) -> filled_latin_v2.csv
- Rest -> needs_human_filtered_v2.csv (for fill_needs_human_withSearch.py)

Run: python apply_curation_rules_v2.py
Then: python fill_needs_human_withSearch.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
NEEDS_HUMAN_FILTERED = DATA_DIR / "needs_human_filtered.csv"
NEEDS_HUMAN_FILTERED_V2 = DATA_DIR / "needs_human_filtered_v2.csv"
FILLED_LATIN_V2 = DATA_DIR / "filled_latin_v2.csv"

FIELDS = ["ingredient", "skin_type", "effect", "confidence"]


def main():
    if not NEEDS_HUMAN_FILTERED.exists():
        print(f"Missing {NEEDS_HUMAN_FILTERED.name}; run filter_needs_human.py first.")
        return

    from fill_curation_rules import match_rule

    rows = []
    with open(NEEDS_HUMAN_FILTERED, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ing = (row.get("ingredient") or "").strip()
            if ing:
                rows.append(ing)

    filled = []
    still_needs = []

    for ing in rows:
        rule = match_rule(ing)
        if rule:
            types, effect, confidence = rule
            skin_type_str = ",".join(types)
            filled.append({
                "ingredient": ing,
                "skin_type": skin_type_str,
                "effect": effect,
                "confidence": confidence,
            })
        else:
            still_needs.append({
                "ingredient": ing,
                "skin_type": "",
                "effect": "",
                "confidence": "",
            })

    with open(FILLED_LATIN_V2, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(filled)
    print(f"filled_latin_v2.csv: {len(filled)} rows (rule-matched)")

    with open(NEEDS_HUMAN_FILTERED_V2, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(still_needs)
    print(f"needs_human_filtered_v2.csv: {len(still_needs)} rows (for withSearch)")


if __name__ == "__main__":
    main()
