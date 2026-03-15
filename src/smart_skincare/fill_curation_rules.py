"""
1) Filter missing_ingredients_for_curation.csv to real-ingredient-like only (drop complex/technology/visibly etc.)
2) Rank by frequency in products, take top 200-500
3) Rule-based fill (confident ones); ambiguous -> confidence=low, effect=neutral
4) Output: filled_rows.csv (auto-filled), needs_human.csv (rest for human/rule-fill)
5) Update missing_ingredients_for_curation.csv with filled rows so build picks them up.

Run: python fill_curation_rules.py
Then: python build_ingredient_skin_map.py
"""
import csv
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"
MISSING_CSV = DATA_DIR / "missing_ingredients_for_curation.csv"
FILLED_ROWS_CSV = DATA_DIR / "filled_rows.csv"
NEEDS_HUMAN_CSV = DATA_DIR / "needs_human.csv"

# Reuse drop logic from fill_missing_ingredient_data
def _normalize(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"^[\s*.\-]+\s*", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


DROP_REGEXES = [
    re.compile(r"^[+\-*/()\s.\d%]+$", re.I),
    re.compile(r"^\d+(\.\d+)?\s*%?\s*$"),
    re.compile(r"^\s*[)\d]\s*$"),
    re.compile(r"\d{2,}%\s*ingredients?", re.I),
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-", re.I),  # uuid
    re.compile(r"^[0-9a-f]{20,}$", re.I),  # long hex
]
DROP_PHRASES = (
    "patented", "proprietary", "full-spectrum", "technology", "delivery system",
    "note:", "may contain", "division ", "visit the", "helps ", "visibly ", "improves ",
    "complex of ", "complex (", "from jackson hole", "thin layers of silk",
    " skin complex", "pore-shrinking complex", "synergen skin complex",
)
DROP_STANDALONE = ("complex", "blend", "matrix", "boost", "inactive")


def should_drop(ing: str) -> bool:
    if not ing or len(ing.strip()) < 2:
        return True
    n = _normalize(ing)
    if len(n) < 3:
        return True
    for r in DROP_REGEXES:
        if r.search(ing) or r.search(n):
            return True
    for phrase in DROP_PHRASES:
        if phrase in n:
            return True
    for kw in DROP_STANDALONE:
        if n == kw or (n.endswith(" " + kw) and len(n[: -len(kw) - 1].strip()) <= 12):
            return True
    # Product-name-like
    if re.search(r"\d+\s*jelly|\d+\s*super|emollients and |naturalizer |vegan and natural tanning", n):
        return True
    return False


# Rule: (pattern substring or exact, skin_types list, effect, confidence)
# Order: more specific first. First match wins.
CURATION_RULES = [
    # Actives / brightening
    ("4msk", ["pigmentation"], "good", "medium"),
    ("4-butylresorcinol", ["pigmentation"], "good", "medium"),
    ("4-ethylresorcinol", ["pigmentation"], "good", "low"),
    ("azelaic", ["oily", "pigmentation"], "good", "medium"),
    ("tranexamic", ["pigmentation"], "good", "medium"),
    ("txa", ["pigmentation"], "good", "low"),
    ("pha", ["oily", "pigmentation"], "good", "medium"),
    ("alpha arbutin", ["pigmentation"], "good", "medium"),
    ("arbutin", ["pigmentation"], "good", "low"),
    ("kojic", ["pigmentation"], "good", "low"),
    ("niacinamide", ["oily", "pigmentation"], "good", "medium"),
    # Minerals / sunscreen
    ("zinc oxide", ["sensitive"], "good", "medium"),
    ("titanium dioxide", ["sensitive"], "good", "medium"),
    ("mica", [], "neutral", "low"),
    ("silicon dioxide", [], "neutral", "low"),
    ("silica", ["oily"], "good", "low"),
    # Peptides / anti-aging
    ("matrixyl", ["wrinkle"], "good", "low"),
    ("palmitoyl pentapeptide", ["wrinkle"], "good", "medium"),
    ("palmitoyl tetrapeptide", ["wrinkle"], "good", "low"),
    ("acetyl hexapeptide", ["wrinkle"], "good", "low"),
    ("copper peptide", ["wrinkle"], "good", "low"),
    ("bakuchiol", ["wrinkle", "sensitive"], "good", "medium"),
    # Plant / adaptogens (conservative)
    ("ashwagandha", ["wrinkle", "sensitive"], "good", "low"),
    ("withania somnifera", ["wrinkle", "sensitive"], "good", "low"),
    ("rhodiola", ["wrinkle", "sensitive"], "good", "low"),
    ("shatavari", ["dry", "sensitive"], "good", "low"),
    ("centella", ["sensitive", "wrinkle"], "good", "low"),
    ("gotu kola", ["sensitive", "wrinkle"], "good", "low"),
    ("tocotrienol", ["pigmentation", "wrinkle"], "good", "low"),
    ("jasminum officinale", ["dry", "sensitive"], "good", "low"),
    ("rosehip", ["dry", "pigmentation"], "good", "low"),
    ("rose hip", ["dry", "pigmentation"], "good", "low"),
    ("meadowfoam", ["dry"], "good", "low"),
    ("grapeseed", ["pigmentation", "wrinkle"], "good", "low"),
    ("grape seed", ["pigmentation", "wrinkle"], "good", "low"),
    ("avocado", ["dry"], "good", "low"),
    ("sunflower", ["dry"], "good", "low"),
    ("jojoba", ["dry"], "good", "low"),
    ("argan", ["dry"], "good", "low"),
    ("marula", ["dry"], "good", "low"),
    ("mango", ["dry"], "good", "low"),
    ("papaya", ["oily", "pigmentation"], "good", "low"),
    ("pineapple", ["oily", "pigmentation"], "good", "low"),
    # Preservatives / solvents (neutral)
    ("1,2-hexanediol", [], "neutral", "low"),
    ("1,2-hexandiol", [], "neutral", "low"),
    ("1,10-decanediol", [], "neutral", "low"),
    ("pentylene glycol", ["dry"], "good", "low"),
    ("caprylyl glycol", [], "neutral", "low"),
    ("phenoxyethanol", [], "neutral", "low"),
    ("sodium benzoate", [], "neutral", "low"),
    ("potassium sorbate", [], "neutral", "low"),
    ("benzyl alcohol", [], "neutral", "low"),
    ("dehydroacetic acid", [], "neutral", "low"),
    # Humectants / barrier
    ("sodium hyaluronate", ["dry", "sensitive"], "good", "medium"),
    ("hyaluronic acid", ["dry", "sensitive"], "good", "medium"),
    ("squalane", ["dry"], "good", "medium"),
    ("squalene", ["dry"], "good", "low"),
    ("glycerin", ["dry", "sensitive"], "good", "medium"),
    ("panthenol", ["dry", "sensitive"], "good", "medium"),
    ("allantoin", ["sensitive"], "good", "medium"),
    ("bisabolol", ["sensitive"], "good", "low"),
    ("ceramide", ["dry", "sensitive"], "good", "medium"),
    ("cholesterol", ["dry", "sensitive"], "good", "low"),
    # Acids
    ("lactic acid", ["oily", "pigmentation", "dry"], "good", "medium"),
    ("glycolic acid", ["oily", "pigmentation"], "good", "medium"),
    ("mandelic acid", ["oily", "pigmentation"], "good", "low"),
    ("salicylic acid", ["oily"], "good", "medium"),
    ("ferulic acid", ["pigmentation", "wrinkle"], "good", "medium"),
    ("linoleic acid", ["dry", "oily"], "good", "low"),
    # CoQ10 / vitamins (alias should map; low if still in list)
    ("coq10", ["pigmentation", "wrinkle"], "good", "low"),
    ("coenzyme q10", ["pigmentation", "wrinkle"], "good", "medium"),
    ("ubiquinone", ["pigmentation", "wrinkle"], "good", "low"),
    # Misc
    ("caffeine", ["oily", "pigmentation"], "good", "low"),
    ("resveratrol", ["pigmentation", "wrinkle"], "good", "medium"),
    ("alpha lipoic acid", ["pigmentation", "wrinkle"], "good", "low"),
    ("licorice", ["sensitive", "pigmentation"], "good", "low"),
    ("green tea", ["pigmentation", "wrinkle"], "good", "medium"),
    ("camellia sinensis", ["pigmentation", "wrinkle"], "good", "low"),
    ("aloe", ["dry", "sensitive"], "good", "medium"),
    ("calendula", ["sensitive"], "good", "low"),
    ("chamomile", ["sensitive"], "good", "low"),
    ("witch hazel", ["oily"], "good", "low"),
    ("hamamelis", ["oily"], "good", "low"),
]


def match_rule(ing: str) -> tuple | None:
    """First matching rule -> (skin_types, effect, confidence)."""
    n = _normalize(ing)
    for pattern, types, effect, conf in CURATION_RULES:
        if pattern in n or n == pattern:
            return (types, effect, conf)
    return None


def main():
    # Load missing CSV
    if not MISSING_CSV.exists():
        print(f"Missing {MISSING_CSV.name}; run fill_missing_ingredient_data.py --export-missing first.")
        return
    rows = []
    with open(MISSING_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            ing = (row.get("ingredient") or "").strip()
            if ing:
                rows.append(row)

    # Filter to real-ingredient-like only
    real = []
    for row in rows:
        ing = (row.get("ingredient") or "").strip()
        if should_drop(ing):
            continue
        real.append(ing)

    # Frequency from products
    from recommend_mvp import load_products_with_ingredients
    products = load_products_with_ingredients(max_products=None)
    freq = Counter()
    real_set = set(real)
    for p in products:
        for ing in (p.get("ingredients") or []):
            if ing and ing in real_set:
                freq[ing] += 1

    # Top 500 by frequency (or all if fewer)
    top_n = 500
    sorted_real = sorted(real_set, key=lambda x: -freq.get(x, 0))[:top_n]

    # Rule fill
    filled = []
    needs_human_list = []
    for ing in sorted_real:
        rule = match_rule(ing)
        if rule:
            types, effect, confidence = rule
            skin_type_str = ",".join(types)
            filled.append({"ingredient": ing, "skin_type": skin_type_str, "effect": effect, "confidence": confidence})
        else:
            # Conservative: neutral, low
            filled.append({"ingredient": ing, "skin_type": "", "effect": "neutral", "confidence": "low"})

    # filled_rows.csv = all top-N we filled (rule-based + conservative neutral/low)
    with open(FILLED_ROWS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ingredient", "skin_type", "effect", "confidence"])
        w.writeheader()
        w.writerows(filled)
    print(f"filled_rows.csv: {len(filled)} rows (top {top_n} by frequency, rule + conservative)")

    # needs_human.csv = rest of real list (not in top 500), for human/rule-fill
    filled_ings = set(sorted_real)
    needs_set = real_set - filled_ings
    needs_sorted = sorted(needs_set)
    with open(NEEDS_HUMAN_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ingredient", "skin_type", "effect", "confidence"])
        w.writeheader()
        for ing in needs_sorted:
            w.writerow({"ingredient": ing, "skin_type": "", "effect": "", "confidence": ""})
    print(f"needs_human.csv: {len(needs_sorted)} rows (for human/rule-fill)")

    # Update missing_ingredients_for_curation.csv: merge all filled into it
    filled_by_ing = {r["ingredient"]: r for r in filled}
    new_rows = []
    with open(MISSING_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            ing = (row.get("ingredient") or "").strip()
            if ing in filled_by_ing:
                row["skin_type"] = filled_by_ing[ing]["skin_type"]
                row["effect"] = filled_by_ing[ing]["effect"]
                row["confidence"] = filled_by_ing[ing]["confidence"]
            new_rows.append(row)

    with open(MISSING_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(new_rows)
    print(f"Updated {MISSING_CSV.name} with {len(filled)} filled rows.")
    print("Run: python build_ingredient_skin_map.py")


if __name__ == "__main__":
    main()
