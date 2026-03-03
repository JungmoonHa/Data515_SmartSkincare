"""
Fill manual_curation.csv from top1000_unmatched_for_curation.csv.
Columns: ingredient, source, skin_type, notes, confidence, effect
- effect: good / avoid / neutral (direction for scoring)
- skin_type: always stored in fixed order (dry, normal, oily, pigmentation, sensitive, wrinkle)
- Defaults: skin_type empty -> effect neutral; confidence empty -> low
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INPUT_CSV = DATA_DIR / "top1000_unmatched_for_curation.csv"
OUTPUT_CSV = DATA_DIR / "manual_curation.csv"

SKIN_TYPES = {"dry", "normal", "oily", "pigmentation", "sensitive", "wrinkle"}
# Fixed order for consistent storage and aggregation
SKIN_TYPE_ORDER = ["dry", "normal", "oily", "pigmentation", "sensitive", "wrinkle"]


def _sort_skin_types(types: list) -> str:
    """Return comma-separated skin_type string in fixed order."""
    if not types:
        return ""
    seen = set()
    ordered = [t for t in SKIN_TYPE_ORDER if t in types and t not in seen and not seen.add(t)]
    return ",".join(ordered)


# (pattern, skin_types, notes, confidence, effect)
RULES = [
    # neutral: base / solvent
    (r"^aqua\b|^water\b|^eau\b|water aqua eau|declustered water", ["normal"], "solvent/base", "high", "neutral"),
    # avoid: fragrance / alcohol
    (r"parfum|fragrance|aroma flavor|natural fragrance|fragrance parfum", ["sensitive"], "fragrance; may irritate", "high", "avoid"),
    (r"alcohol denat", ["oily", "sensitive"], "denat alcohol; can dry or irritate", "high", "avoid"),
    # good: soothing / calming
    (r"aloe barbadensis|aloe vera", ["dry", "sensitive"], "soothing, hydrating", "high", "good"),
    (r"hamamelis virginiana|witch hazel", ["oily", "sensitive"], "astringent, soothing", "high", "good"),
    (r"chamomilla recutita|anthemis nobilis|chamomile", ["sensitive", "dry"], "soothing, anti-inflammatory", "high", "good"),
    (r"centella|tiger grass|gotu kola", ["sensitive", "wrinkle"], "soothing, barrier", "high", "good"),
    (r"oat extract|avena sativa|colloidal oatmeal", ["sensitive", "dry"], "soothing, moisturizing", "high", "good"),
    (r"allantoin", ["sensitive", "dry"], "soothing, healing", "high", "good"),
    (r"bisabolol", ["sensitive"], "soothing", "high", "good"),
    (r"licorice|glycyrrhiza", ["sensitive", "pigmentation"], "soothing, brightening", "high", "good"),
    # good: oils
    (r"seed oil|fruit oil|nut oil|kernel oil", ["dry"], "emollient", "medium", "good"),
    (r"jojoba|simmondsia chinensis", ["dry", "oily"], "balancing oil", "high", "good"),
    (r"rose hip|rosa canina", ["dry", "wrinkle"], "emollient, vitamin", "high", "good"),
    (r"argan oil|argania spinosa", ["dry", "wrinkle"], "emollient, antioxidant", "high", "good"),
    (r"sea buckthorn|hippophae rhamnoides", ["dry", "wrinkle"], "omega, vitamin", "high", "good"),
    (r"olive oil|olea europaea.*oil", ["dry"], "emollient", "medium", "good"),
    (r"sunflower seed|helianthus annuus", ["dry"], "emollient", "medium", "good"),
    (r"macadamia.*oil|macadamia integrifolia", ["dry"], "emollient", "medium", "good"),
    (r"camellia.*seed oil|camellia oleifera", ["dry", "wrinkle"], "emollient, antioxidant", "medium", "good"),
    (r"squalane|squalene", ["dry", "oily"], "light emollient", "high", "good"),
    (r"shea butter|butyrospermum parkii", ["dry"], "emollient", "high", "good"),
    (r"coconut oil|cocos nucifera.*oil", ["dry"], "emollient", "medium", "good"),
    (r"avocado oil|persea gratissima", ["dry", "wrinkle"], "emollient", "medium", "good"),
    (r"grape seed|vitis vinifera.*seed", ["oily", "wrinkle"], "antioxidant", "medium", "good"),
    (r"carrot seed|daucus carota.*seed", ["dry", "wrinkle"], "antioxidant, vitamin", "medium", "good"),
    # good: ferment
    (r"ferment|saccharomyces|bacillus ferment|lactobacillus|leuconostoc", ["wrinkle", "pigmentation"], "ferment/probiotic", "medium", "good"),
    (r"yeast extract|faex|extrait de levure", ["wrinkle"], "yeast", "medium", "good"),
    (r"galactomyces|bifida ferment", ["wrinkle", "pigmentation"], "ferment", "high", "good"),
    # good: antioxidant / vitamin
    (r"camellia sinensis|green tea", ["oily", "wrinkle"], "antioxidant", "high", "good"),
    (r"niacinamide|niacin\b", ["pigmentation", "oily"], "brightening, barrier", "high", "good"),
    (r"ascorb|vitamin c|ascorbic", ["pigmentation", "wrinkle"], "antioxidant, brightening", "high", "good"),
    (r"retinol|retinal|retinyl", ["wrinkle"], "cell turnover", "high", "good"),
    (r"tocopherol|tocopheryl|vitamin e", ["dry", "wrinkle"], "antioxidant", "high", "good"),
    (r"vitamin a|retinol", ["wrinkle"], "anti-aging", "high", "good"),
    # good: hydration
    (r"hyaluron|sodium hyaluronate|ha\b", ["dry"], "humectant", "high", "good"),
    (r"glycerin|glycerol", ["dry", "normal"], "humectant", "high", "good"),
    (r"urea\b", ["dry"], "humectant", "high", "good"),
    (r"trehalose", ["dry"], "humectant", "medium", "good"),
    (r"sodium pca", ["dry"], "humectant", "medium", "good"),
    # good: exfoliant
    (r"salicylic|bha", ["oily"], "exfoliant", "high", "good"),
    (r"glycolic|aha|alpha hydroxy", ["oily", "wrinkle"], "exfoliant", "high", "good"),
    (r"lactic acid", ["dry", "wrinkle"], "gentle exfoliant", "high", "good"),
    (r"phytic acid", ["pigmentation", "oily"], "gentle exfoliant", "medium", "good"),
    # good: botanicals
    (r"rose extract|rosa damascena|rosa canina", ["dry", "sensitive"], "soothing, antioxidant", "medium", "good"),
    (r"lavender|lavandula", ["sensitive"], "soothing (can irritate some)", "medium", "good"),
    (r"calendula", ["sensitive", "dry"], "soothing", "medium", "good"),
    (r"cucumber|cucumis", ["sensitive", "dry"], "soothing, hydrating", "medium", "good"),
    (r"ginkgo biloba", ["wrinkle"], "antioxidant", "medium", "good"),
    (r"resveratrol", ["wrinkle"], "antioxidant", "high", "good"),
    (r"coffee|coffea", ["oily", "wrinkle"], "antioxidant", "medium", "good"),
    (r"mushroom|tremella", ["dry", "wrinkle"], "hydration, antioxidant", "medium", "good"),
    (r"propolis", ["sensitive", "dry"], "soothing, antibacterial", "medium", "good"),
    (r"honey|mel\b|miel", ["dry", "sensitive"], "humectant, soothing", "medium", "good"),
    (r"royal jelly", ["dry", "wrinkle"], "nourishing", "medium", "good"),
    (r"rice extract|oryza sativa", ["dry", "pigmentation"], "soothing, brightening", "medium", "good"),
    (r"soy extract|glycine soja", ["wrinkle", "pigmentation"], "antioxidant", "medium", "good"),
    (r"morus alba|mulberry", ["pigmentation"], "brightening", "medium", "good"),
    (r"bearberry|arctostaphylos", ["pigmentation"], "brightening", "medium", "good"),
    (r"polypeptide|oligopeptide|peptide", ["wrinkle"], "signal peptide", "medium", "good"),
    (r"sh-polypeptide|sh-oligopeptide", ["wrinkle"], "signal peptide", "medium", "good"),
    (r"zinc oxide|zinc pca", ["oily", "sensitive"], "soothing, oil control", "medium", "good"),
    (r"witch hazel", ["oily"], "astringent", "high", "good"),
    # neutral: color / UV / formulation
    (r"titanium dioxide|ci 77891", ["normal"], "UV/color", "high", "neutral"),
    (r"iron oxide|ci 77491|ci 77492|ci 77499", ["normal"], "color", "high", "neutral"),
    (r"mica|ci 77", ["normal"], "color", "medium", "neutral"),
    (r"acrylate|copolymer|crosspolymer|peg-|ppg-|dimethicone", ["normal"], "formulation", "low", "neutral"),
    (r"carbomer|xanthan|gum\b", ["normal"], "thickener", "low", "neutral"),
    (r"phenoxyethanol", ["normal"], "preservative", "medium", "neutral"),
    (r"caprylyl glycol", ["normal"], "preservative", "medium", "neutral"),
    (r"benzyl alcohol", ["normal"], "preservative", "medium", "neutral"),
    # good: more botanicals
    (r"flower extract|flower water", ["sensitive", "dry"], "botanical", "low", "good"),
    (r"leaf extract|leaf water", ["wrinkle", "dry"], "botanical extract", "low", "good"),
    (r"root extract", ["wrinkle", "sensitive"], "botanical", "low", "good"),
    (r"fruit extract|fruit oil", ["wrinkle", "pigmentation"], "vitamin/antioxidant", "low", "good"),
    (r"seed extract", ["dry", "wrinkle"], "botanical", "low", "good"),
    (r"bark extract", ["wrinkle"], "antioxidant", "low", "good"),
    (r"marine extract|algae extract|seaweed|sea water", ["dry", "wrinkle"], "minerals, hydration", "low", "good"),
    (r"extract\b.*extract|extract$", ["normal"], "botanical extract", "low", "good"),
    (r"\boil\b|oil,", ["dry"], "emollient", "low", "good"),
    (r"butter\b", ["dry"], "emollient", "low", "good"),
    (r"ester\b|esters\b", ["dry"], "emollient", "low", "good"),
    (r"wax\b", ["dry"], "emollient/barrier", "low", "good"),
    (r"citric acid|sodium citrate", ["normal"], "pH/chelator", "low", "neutral"),
    (r"malic acid|tartaric", ["wrinkle"], "AHA", "low", "good"),
    (r"sodium chloride|potassium chloride|sea salt|maris sal", ["normal"], "mineral", "low", "neutral"),
    (r"magnesium|zinc sulfate|calcium", ["normal"], "mineral", "low", "neutral"),
    (r"visit the|no info|#name\?|ingredients from organic", [], "", "low", "neutral"),
]


def match_rules(ingredient: str) -> tuple:
    """Return (skin_types, notes, confidence, effect)."""
    ing_lower = ingredient.strip().lower()
    for pattern, types, notes, conf, effect in RULES:
        if re.search(pattern, ing_lower, re.I):
            return (types, notes, conf, effect)
    return ([], "", "low", "neutral")


def is_junk(ingredient: str) -> bool:
    if not ingredient or len(ingredient.strip()) < 3:
        return True
    ing = ingredient.strip().lower()
    if "visit the" in ing or "no info" in ing or "#name" in ing:
        return True
    if ing.startswith("ci 77") and ")" in ing:
        return True
    return False


def main():
    rows = []
    with open(INPUT_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ing = (row.get("ingredient") or "").strip()
            if not ing or is_junk(ing):
                rows.append({
                    "ingredient": ing, "source": "", "skin_type": "", "notes": "",
                    "confidence": "low", "effect": "neutral",
                })
                continue
            types, notes, conf, effect = match_rules(ing)
            # skin_type NaN -> effect neutral (already in match_rules default)
            # confidence NaN -> low
            conf = (conf or "").strip() or "low"
            effect = (effect or "").strip() or "neutral"
            skin_type_str = _sort_skin_types([t for t in types if t in SKIN_TYPES])
            rows.append({
                "ingredient": ing,
                "source": "manual",
                "skin_type": skin_type_str,
                "notes": notes,
                "confidence": conf,
                "effect": effect,
            })

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ingredient", "source", "skin_type", "notes", "confidence", "effect"])
        w.writeheader()
        w.writerows(rows)

    filled = sum(1 for r in rows if (r.get("skin_type") or "").strip())
    with_effect = sum(1 for r in rows if (r.get("effect") or "").strip())
    print(f"Wrote {OUTPUT_CSV.name}: {len(rows)} rows, {filled} with skin_type, {with_effect} with effect.")
    print("Run: python build_ingredient_skin_map.py")


if __name__ == "__main__":
    main()
