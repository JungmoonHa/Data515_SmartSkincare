"""
Fill needs_human_filtered_v2.csv with rule-based + keyword heuristics (withSearch).
Output: withSearch_filled_v2.csv (ingredient, skin_type, effect, confidence).
Build loads this via load_withSearch_filled_v2() and merges into ingredient_skin_map.

Run: python fill_needs_human_withSearch.py
Then: python build_ingredient_skin_map.py
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"
NEEDS_HUMAN_V2 = DATA_DIR / "needs_human_filtered_v2.csv"
WITHSEARCH_FILLED_V2 = DATA_DIR / "withSearch_filled_v2.csv"

SKIN_TYPES = {"dry", "normal", "oily", "pigmentation", "sensitive", "wrinkle"}


def _normalize(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"^[\s*.\-]+\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# Reuse rules from fill_curation_rules (subset + extended for v2 list)
def _match_curation_rules(ing: str) -> tuple | None:
    """(skin_types list, effect, confidence) or None."""
    from fill_curation_rules import match_rule
    r = match_rule(ing)
    return r


# Keyword patterns: (substring or regex, skin_types, effect, confidence)
# First match wins. Order: specific first.
KEYWORD_RULES = [
    # Avoid / irritants
    (r"propellant|aerosol|a\s*70\s*propellant", [], "avoid", "low"),
    ("fragrance", ["sensitive"], "avoid", "medium"),
    ("parfum", ["sensitive"], "avoid", "medium"),
    ("alpha-hexylcinnamaldehyde", ["sensitive"], "avoid", "low"),
    ("alpha-isomethyl ionone", ["sensitive"], "avoid", "low"),
    ("limonene", ["sensitive"], "avoid", "low"),
    ("linalool", ["sensitive"], "avoid", "low"),
    ("citral", ["sensitive"], "avoid", "low"),
    ("eugenol", ["sensitive"], "avoid", "low"),
    ("benzophenone", [], "avoid", "low"),
    ("denat alcohol", [], "avoid", "low"),
    ("alcohol denat", [], "avoid", "low"),
    # Actives / brightening
    ("4msk", ["pigmentation"], "good", "medium"),
    ("4-butylresorcinol", ["pigmentation"], "good", "medium"),
    ("4-ethylresorcinol", ["pigmentation"], "good", "low"),
    ("tranexamic", ["pigmentation"], "good", "medium"),
    ("txa", ["pigmentation"], "good", "low"),
    ("azelaic", ["oily", "pigmentation"], "good", "medium"),
    ("arbutin", ["pigmentation"], "good", "low"),
    ("kojic", ["pigmentation"], "good", "low"),
    ("niacinamide", ["oily", "pigmentation"], "good", "medium"),
    ("pha", ["oily", "pigmentation"], "good", "medium"),
    ("retinol", ["wrinkle"], "good", "medium"),
    ("retinal", ["wrinkle"], "good", "low"),
    ("bakuchiol", ["wrinkle", "sensitive"], "good", "medium"),
    ("ascorbic", ["pigmentation", "wrinkle"], "good", "medium"),
    ("vitamin c", ["pigmentation", "wrinkle"], "good", "medium"),
    ("tocopherol", ["pigmentation", "wrinkle"], "good", "low"),
    ("vitamin e", ["pigmentation", "wrinkle"], "good", "low"),
    ("ferulic", ["pigmentation", "wrinkle"], "good", "medium"),
    ("resveratrol", ["pigmentation", "wrinkle"], "good", "low"),
    ("coq10", ["pigmentation", "wrinkle"], "good", "low"),
    ("ubiquinone", ["pigmentation", "wrinkle"], "good", "low"),
    ("antioxidant coq10", ["pigmentation", "wrinkle"], "good", "low"),
    # Peptides / anti-aging
    ("peptide", ["wrinkle"], "good", "low"),
    ("matrixyl", ["wrinkle"], "good", "low"),
    ("palmitoyl", ["wrinkle"], "good", "low"),
    ("acetyl hexapeptide", ["wrinkle"], "good", "low"),
    ("copper peptide", ["wrinkle"], "good", "low"),
    ("collagen", ["wrinkle", "dry"], "good", "low"),
    ("elastin", ["wrinkle"], "good", "low"),
    # Acids / exfoliants
    ("glycolic", ["oily", "pigmentation"], "good", "medium"),
    ("lactic acid", ["oily", "pigmentation", "dry"], "good", "medium"),
    ("salicylic", ["oily"], "good", "medium"),
    ("mandelic", ["oily", "pigmentation"], "good", "low"),
    ("aha", ["oily", "pigmentation"], "good", "low"),
    ("bha", ["oily"], "good", "low"),
    # Humectants / barrier
    ("hyaluron", ["dry", "sensitive"], "good", "medium"),
    ("sodium hyaluronate", ["dry", "sensitive"], "good", "medium"),
    ("glycerin", ["dry", "sensitive"], "good", "medium"),
    ("panthenol", ["dry", "sensitive"], "good", "medium"),
    ("allantoin", ["sensitive"], "good", "medium"),
    ("bisabolol", ["sensitive"], "good", "low"),
    ("ceramide", ["dry", "sensitive"], "good", "medium"),
    ("squalane", ["dry"], "good", "medium"),
    ("squalene", ["dry"], "good", "low"),
    ("cholesterol", ["dry", "sensitive"], "good", "low"),
    ("pentylene glycol", ["dry"], "good", "low"),
    ("1,2-hexanediol", [], "neutral", "low"),
    ("1,2-heanediol", [], "neutral", "low"),
    ("1,2-hexanidiol", [], "neutral", "low"),
    ("caprylyl glycol", [], "neutral", "low"),
    ("phenoxyethanol", [], "neutral", "low"),
    ("sodium benzoate", [], "neutral", "low"),
    ("potassium sorbate", [], "neutral", "low"),
    ("benzyl alcohol", [], "neutral", "low"),
    # Oils / emollients (plant)
    ("oil", ["dry"], "good", "low"),
    (" butter", ["dry"], "good", "low"),
    (" seed oil", ["dry"], "good", "low"),
    (" kernel oil", ["dry"], "good", "low"),
    ("avocado", ["dry"], "good", "low"),
    ("jojoba", ["dry"], "good", "low"),
    ("argan", ["dry"], "good", "low"),
    ("marula", ["dry"], "good", "low"),
    ("sunflower", ["dry"], "good", "low"),
    ("grapeseed", ["pigmentation", "wrinkle"], "good", "low"),
    ("grape seed", ["pigmentation", "wrinkle"], "good", "low"),
    ("rosehip", ["dry", "pigmentation"], "good", "low"),
    ("rose hip", ["dry", "pigmentation"], "good", "low"),
    ("meadowfoam", ["dry"], "good", "low"),
    ("mango", ["dry"], "good", "low"),
    ("papaya", ["oily", "pigmentation"], "good", "low"),
    ("pineapple", ["oily", "pigmentation"], "good", "low"),
    ("almond", ["dry"], "good", "low"),
    ("borage", ["dry"], "good", "low"),
    ("borago", ["dry"], "good", "low"),
    ("black cumin", ["dry", "sensitive"], "good", "low"),
    ("tea tree", ["oily"], "good", "low"),
    ("neem", ["oily", "sensitive"], "good", "low"),
    # Extracts / botanicals
    (" extract", ["dry", "sensitive", "wrinkle"], "good", "low"),
    ("extract", ["dry", "sensitive", "wrinkle"], "good", "low"),
    ("aloe", ["dry", "sensitive"], "good", "medium"),
    ("centella", ["sensitive", "wrinkle"], "good", "low"),
    ("gotu kola", ["sensitive", "wrinkle"], "good", "low"),
    ("green tea", ["pigmentation", "wrinkle"], "good", "medium"),
    ("camellia sinensis", ["pigmentation", "wrinkle"], "good", "low"),
    ("calendula", ["sensitive"], "good", "low"),
    ("chamomile", ["sensitive"], "good", "low"),
    ("licorice", ["sensitive", "pigmentation"], "good", "low"),
    ("witch hazel", ["oily"], "good", "low"),
    ("hamamelis", ["oily"], "good", "low"),
    ("ashwagandha", ["wrinkle", "sensitive"], "good", "low"),
    ("rhodiola", ["wrinkle", "sensitive"], "good", "low"),
    ("caffeine", ["oily", "pigmentation"], "good", "low"),
    ("acerola", ["wrinkle", "pigmentation"], "good", "low"),
    ("blueberry", ["pigmentation", "wrinkle"], "good", "low"),
    ("pomegranate", ["pigmentation", "wrinkle"], "good", "low"),
    ("tremella", ["dry"], "good", "low"),
    ("tremella fuciformis", ["dry"], "good", "low"),
    ("bamboo", ["oily", "sensitive"], "good", "low"),
    ("oat", ["dry", "sensitive"], "good", "low"),
    ("avena sativa", ["dry", "sensitive"], "good", "low"),
    ("artichoke", ["sensitive"], "good", "low"),
    ("sea kelp", ["dry", "sensitive"], "good", "low"),
    ("kelp", ["dry"], "good", "low"),
    ("chaga", ["wrinkle"], "good", "low"),
    ("reishi", ["wrinkle", "sensitive"], "good", "low"),
    ("shiitake", ["wrinkle"], "good", "low"),
    ("mushroom", ["wrinkle", "sensitive"], "good", "low"),
    ("boswellia", ["sensitive"], "good", "low"),
    ("turmeric", ["sensitive", "pigmentation"], "good", "low"),
    ("curcuma", ["sensitive", "pigmentation"], "good", "low"),
    ("ginger", ["sensitive"], "good", "low"),
    ("lavender", ["sensitive"], "good", "low"),
    ("bergamot", ["sensitive"], "good", "low"),
    ("rose", ["dry", "sensitive"], "good", "low"),
    ("jasmine", ["dry", "sensitive"], "good", "low"),
    ("safflower", ["dry"], "good", "low"),
    ("olive", ["dry"], "good", "low"),
    ("beet", ["pigmentation"], "good", "low"),
    ("beetroot", ["pigmentation"], "good", "low"),
    ("sugar beet", [], "neutral", "low"),
    ("carrot", ["dry", "pigmentation"], "good", "low"),
    ("cucumber", ["sensitive"], "good", "low"),
    ("apple", ["pigmentation"], "good", "low"),
    ("acv", ["oily"], "good", "low"),
    ("apple cider vinegar", ["oily"], "good", "low"),
    ("vitamin", ["wrinkle", "pigmentation"], "good", "low"),
    ("mineral", [], "neutral", "low"),
    ("zinc oxide", ["sensitive"], "good", "medium"),
    ("titanium dioxide", ["sensitive"], "good", "medium"),
    ("silica", ["oily"], "good", "low"),
    ("mica", [], "neutral", "low"),
    ("gold", [], "neutral", "low"),
    ("24k gold", [], "neutral", "low"),
    ("silver", [], "neutral", "low"),
    ("clay", ["oily"], "good", "low"),
    ("kaolin", ["oily"], "good", "low"),
    ("charcoal", ["oily"], "good", "low"),
    ("adaptogen", ["wrinkle", "sensitive"], "good", "low"),
    ("adaptogens", ["wrinkle", "sensitive"], "good", "low"),
    ("emollient", ["dry"], "good", "low"),
    ("humectant", ["dry"], "good", "low"),
    ("spf", ["sensitive", "pigmentation"], "good", "low"),
    ("broad-spectrum", ["sensitive", "pigmentation"], "good", "low"),
    ("sunscreen", ["sensitive", "pigmentation"], "good", "low"),
    ("omega", ["dry", "wrinkle"], "good", "low"),
    ("omega-3", ["dry", "wrinkle"], "good", "low"),
    ("omega-6", ["dry"], "good", "low"),
    ("linoleic", ["dry", "oily"], "good", "low"),
    ("ceramide", ["dry", "sensitive"], "good", "medium"),
    ("na-pca", ["dry"], "good", "low"),
    ("glucosamine", ["dry", "pigmentation"], "good", "low"),
    ("acetyl glucosamine", ["dry", "pigmentation"], "good", "low"),
    ("lactobacillus", ["sensitive"], "good", "low"),
    ("ferment", ["sensitive", "dry"], "good", "low"),
    ("bifida", ["sensitive"], "good", "low"),
    ("galactomyces", ["pigmentation", "wrinkle"], "good", "low"),
    ("nucleotides", ["wrinkle"], "good", "low"),
    ("algae", ["dry", "sensitive"], "good", "low"),
    ("seaweed", ["dry"], "good", "low"),
    ("aquamin", ["dry"], "good", "low"),
    ("arrowroot", [], "neutral", "low"),
    ("starch", [], "neutral", "low"),
    ("cellulose", [], "neutral", "low"),
    ("xanthan", [], "neutral", "low"),
    ("carbomer", [], "neutral", "low"),
    ("acrylate", [], "neutral", "low"),
    ("dimethicone", [], "neutral", "low"),
    ("cyclomethicone", [], "neutral", "low"),
    ("silicon", [], "neutral", "low"),
    ("peg-", [], "neutral", "low"),
    ("cetearyl", [], "neutral", "low"),
    ("stearyl", [], "neutral", "low"),
    ("cetyl", [], "neutral", "low"),
    ("isostearate", [], "neutral", "low"),
    ("palmitate", [], "neutral", "low"),
    ("stearate", [], "neutral", "low"),
    ("oleate", [], "neutral", "low"),
    ("acetate", [], "neutral", "low"),
    ("phosphate", [], "neutral", "low"),
    ("hydroxide", [], "neutral", "low"),
    ("chloride", [], "neutral", "low"),
    ("sulfate", [], "neutral", "low"),
    ("benzoate", [], "neutral", "low"),
    ("sorbate", [], "neutral", "low"),
    ("ammonium", [], "neutral", "low"),
    ("sodium ", [], "neutral", "low"),
    ("potassium ", [], "neutral", "low"),
    ("calcium ", [], "neutral", "low"),
    ("magnesium ", [], "neutral", "low"),
    ("aluminum", [], "neutral", "low"),
    ("aluminium", [], "neutral", "low"),
    ("oxide", [], "neutral", "low"),
    ("citrate", [], "neutral", "low"),
    ("lactate", [], "neutral", "low"),
    ("gluconate", [], "neutral", "low"),
    ("edta", [], "neutral", "low"),
    ("bht", [], "neutral", "low"),
    ("tocopherol", ["pigmentation", "wrinkle"], "good", "low"),
    ("apigenin", ["sensitive", "wrinkle"], "good", "low"),
    ("betaline", [], "neutral", "low"),
    ("betaine", ["dry"], "good", "low"),
]


def _match_keyword_rules(ing: str) -> tuple | None:
    n = _normalize(ing)
    for rule in KEYWORD_RULES:
        if len(rule) == 4:
            pat, types, effect, conf = rule
            if isinstance(pat, str) and ("|" in pat or "\\" in pat or "(" in pat):
                matched = bool(re.search(pat, n, re.I))
            else:
                matched = pat in n if isinstance(pat, str) else False
            if matched:
                return (types, effect, conf)
    return None


def fill_row(ing: str) -> tuple:
    """Return (skin_type_str, effect, confidence)."""
    ing = (ing or "").strip()
    if not ing:
        return ("", "neutral", "low")

    # 1) Curation rules from fill_curation_rules
    r = _match_curation_rules(ing)
    if r:
        types, effect, conf = r
        return (",".join(types), effect, conf)

    # 2) Keyword rules (substring/regex)
    r = _match_keyword_rules(ing)
    if r:
        types, effect, conf = r
        return (",".join(types), effect, conf)

    # 3) Sentence-like or marketing fragment -> neutral
    n = _normalize(ing)
    if any(x in n for x in (" and ", " for ", " with ", " that ", " in a ", " to ", " the ")):
        if len(n) > 40:
            return ("", "neutral", "low")
    if n.startswith("and ") or n.startswith("with ") or "aqua" in n and len(n) > 30:
        return ("", "neutral", "low")

    # 4) Default: minimal impact
    return ("normal", "neutral", "low")


def main():
    if not NEEDS_HUMAN_V2.exists():
        print(f"Missing {NEEDS_HUMAN_V2.name}; run apply_curation_rules_v2.py first.")
        return

    rows = []
    with open(NEEDS_HUMAN_V2, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ing = (row.get("ingredient") or "").strip()
            if not ing:
                continue
            st = (row.get("skin_type") or "").strip()
            effect = (row.get("effect") or "").strip().lower()
            conf = (row.get("confidence") or "").strip().lower()
            if st or effect:
                rows.append({"ingredient": ing, "skin_type": st, "effect": effect or "neutral", "confidence": conf or "low"})
            else:
                skin_type_str, eff, confidence = fill_row(ing)
                rows.append({"ingredient": ing, "skin_type": skin_type_str, "effect": eff, "confidence": confidence})

    with open(WITHSEARCH_FILLED_V2, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ingredient", "skin_type", "effect", "confidence"])
        w.writeheader()
        w.writerows(rows)

    filled_count = sum(1 for r in rows if (r.get("skin_type") or "").strip() or (r.get("effect") or "").strip())
    print(f"withSearch_filled_v2.csv: {len(rows)} rows (filled: {filled_count})")
    print(f"Run: python build_ingredient_skin_map.py")


if __name__ == "__main__":
    main()
