"""
Fill skin-type data for product ingredients that are missing from ingredient_skin_map.

Strategies:
1. Substring propagation: if a missing ingredient contains a known map key (e.g. 
   "sodium hyaluronate crosspolymer" contains "sodium hyaluronate"), use that entry
   with confidence=low.
2. (Optional) Extend fallback in recommend_mvp for remaining by adding more keywords.

Output: inferred_ingredient_skin_map.json (ingredient -> { skin_types, effect, confidence }).
Merge: run merge_inferred_into_skin_map() to add these into ingredient_skin_map.json
       without overwriting existing entries.

Usage:
  python fill_missing_ingredient_data.py              # generate inferred_ingredient_skin_map.json
  python fill_missing_ingredient_data.py --export-missing   # also write still-missing to missing_ingredients_for_curation.csv
  python fill_missing_ingredient_data.py --merge     # (optional) merge inferred into ingredient_skin_map.json now
  # Or: fill missing_ingredients_for_curation.csv (skin_type, effect, confidence), then run build_ingredient_skin_map.py
  #     build_ingredient_skin_map.py loads 6types + inferred + missing_ingredients_for_curation + manual_curation.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
INGREDIENT_SKIN_MAP_PATH = CACHE_DIR / "ingredient_skin_map.json"
INFERRED_OUTPUT_PATH = CACHE_DIR / "inferred_ingredient_skin_map.json"
MISSING_FOR_CURATION_PATH = DATA_DIR / "missing_ingredients_for_curation.csv"


def _normalize(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"^[\s*.\-]+\s*", "", s)   # leading bullets * - .
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# --- Drop list: not ingredients, exclude from export (and from "missing" for curation) ---
DROP_REGEXES = [
    re.compile(r"^[+\-*/()\s.\d%]+$", re.I),           # only symbols/digits/%
    re.compile(r"^\d+(\.\d+)?\s*%?\s*$"),                 # just number or number%
    re.compile(r"^\s*[)\d]\s*$"),                         # ) 4, ) 6
    re.compile(r"^\s*[+\-]\s*$"),                         # +, -
    re.compile(r"\d{2,}%\s*ingredients?", re.I),         # 70%ingredients, 126%
    re.compile(r"100%\s*(?:medical grade\s*)?silicone", re.I),
    re.compile(r"100%\s*pu\s*foam", re.I),
    re.compile(r"aluminium ferrule|plastic handle|synthetic bristles", re.I),
    re.compile(r"address the causes of|helps?\s|visibly\s|improves?\s|please consult|may contain", re.I),
    re.compile(r"division\s|visit the\s|capsule\s|handle\s*$", re.I),
]
# If token contains any of these (as phrase), always drop
DROP_PHRASES = (
    "patented", "proprietary", "full-spectrum", "technology", "delivery system",
    "note:", "may contain", "division ", "visit the", "helps ", "visibly ", "improves ",
    "complex of ", "complex (", "from jackson hole", "thin layers of silk",
)
# Drop only when token is mostly this (e.g. "complex" alone or "xyz complex" with short xyz)
DROP_STANDALONE = ("complex", "blend", "matrix", "boost")


def should_drop_ingredient(ing: str) -> bool:
    """True if this should never be treated as an ingredient (export/manual_curation excluded)."""
    if not ing or len(ing.strip()) < 2:
        return True
    n = _normalize(ing)
    if len(n) < 2:
        return True
    for r in DROP_REGEXES:
        if r.search(ing) or r.search(n):
            return True
    for phrase in DROP_PHRASES:
        if phrase in n:
            return True
    for kw in DROP_STANDALONE:
        if n == kw:
            return True
        if n.endswith(" " + kw):
            # "kurenai-trulift complex" -> drop; "peptide complex" keep if peptide is long
            prefix = n[: -len(kw) - 1].strip()
            if len(prefix) <= 12 or not re.search(r"[a-z]{4,}", prefix):
                return True
    return False


def strip_percent_and_strength(ing: str) -> tuple[str, str | None]:
    """
    Remove percentage parts from string; return (normalized_ingredient_name, strength_hint or None).
    E.g. '15% blend of azelaic' -> ('blend of azelaic', '15%'); '3% TXA' -> ('txa', '3%').
    """
    s = ing.strip()
    strength_hint = None
    # Capture \d+(.\d+)?\s*% for strength_hint
    pct = re.findall(r"\b(\d+(?:\.\d+)?\s*%)\b", s, re.I)
    if pct:
        strength_hint = pct[0].strip() if pct else None
    # Remove all "N%" parts (with optional leading/trailing spaces)
    s = re.sub(r"\b\d+(?:\.\d+)?\s*%\s*", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return (ing, strength_hint)
    return (_normalize(s), strength_hint)


def is_real_ingredient_candidate(ing: str) -> bool:
    """True if normalized string looks like a plausible INCI (min length, has letters)."""
    n = _normalize(ing)
    if len(n) < 3:
        return False
    if not re.search(r"[a-z]", n):
        return False
    if re.match(r"^[\d\s.%\-+]+$", n):
        return False
    return True


def load_skin_map() -> dict:
    if not INGREDIENT_SKIN_MAP_PATH.exists():
        return {}
    with open(INGREDIENT_SKIN_MAP_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_missing_ingredients(skin_map: dict) -> set:
    """Product ingredients that are not in skin_map and have no fallback."""
    from recommend_mvp import (
        load_products_with_ingredients,
        fallback_entry_from_family,
    )
    products = load_products_with_ingredients(max_products=None)
    products = [p for p in products if not p.get("exclude_recommendation")]
    all_ings = set()
    for p in products:
        for ing in (p.get("ingredients") or []):
            if ing:
                all_ings.add(ing)
    missing = set()
    for ing in all_ings:
        if ing in skin_map:
            continue
        if fallback_entry_from_family(ing) is not None:
            continue
        missing.add(ing)
    return missing


def _entry_to_inferred(entry) -> dict | None:
    if isinstance(entry, dict) and entry.get("skin_types"):
        return {
            "skin_types": list(entry.get("skin_types", [])),
            "effect": entry.get("effect", "good"),
            "confidence": "low",
        }
    if isinstance(entry, list):
        return {"skin_types": list(entry), "effect": "good", "confidence": "low"}
    return None


def infer_from_substring(norm_missing: str, map_keys_sorted_by_len: list, skin_map: dict) -> dict | None:
    """Longest map key that is a substring of norm_missing -> use that entry with confidence=low."""
    if not norm_missing or len(norm_missing) < 3:
        return None
    for map_key in map_keys_sorted_by_len:
        norm_key = _normalize(map_key)
        if not norm_key or len(norm_key) < 4 or len(norm_key) > len(norm_missing):
            continue
        if norm_key in norm_missing:
            entry = skin_map.get(map_key)
            return _entry_to_inferred(entry)
    return None


# Simple name-based rules for ingredients that have no substring match (low confidence)
# Order: more specific patterns first.
NAME_BASED_RULES = (
    ("retinol", ["wrinkle", "pigmentation"], "good"),
    ("retinal", ["wrinkle", "pigmentation"], "good"),
    ("retinyl", ["wrinkle", "pigmentation"], "good"),
    ("bakuchiol", ["wrinkle", "sensitive"], "good"),
    ("ascorb", ["pigmentation", "wrinkle"], "good"),
    ("tocopher", ["pigmentation", "wrinkle"], "good"),
    ("niacinamide", ["oily", "pigmentation"], "good"),
    ("panthenol", ["dry", "sensitive"], "good"),
    ("collagen", ["wrinkle", "dry"], "good"),
    ("elastin", ["wrinkle"], "good"),
    ("keratin", ["dry"], "good"),
    ("squalane", ["dry"], "good"),
    ("squalene", ["dry"], "good"),
    ("ceramide", ["dry", "sensitive"], "good"),
    ("hyaluron", ["dry", "sensitive"], "good"),
    ("glycerin", ["dry", "sensitive"], "good"),
    ("glycerol", ["dry", "sensitive"], "good"),
    ("peptide", ["wrinkle"], "good"),
    (" extract", ["pigmentation", "wrinkle"], "good"),
    (" ferment", ["pigmentation", "wrinkle"], "good"),
    (" oil", ["dry"], "good"),
    (" butter", ["dry"], "good"),
    (" wax", ["dry"], "good"),
    (" alcohol", ["oily"], "good"),
    (" acid", ["oily", "pigmentation"], "good"),
    (" water", [], "neutral"),
    (" silica", ["oily"], "good"),
    (" starch", [], "neutral"),
    (" clay", ["oily"], "good"),
    (" kaolin", ["oily"], "good"),
    (" bentonite", ["oily"], "good"),
    (" polymer", [], "neutral"),
    (" dimethicone", ["dry"], "good"),
    (" cyclopentasiloxane", [], "neutral"),
    (" sulfate", [], "neutral"),
    (" citrate", [], "neutral"),
    (" acetate", [], "neutral"),
    (" benzoate", [], "neutral"),
    (" sorbate", [], "neutral"),
    (" paraben", [], "neutral"),
    (" polysaccharide", ["dry", "sensitive"], "good"),
    (" gum", [], "neutral"),
    (" cellulose", [], "neutral"),
    (" xanthan", [], "neutral"),
    (" carbomer", [], "neutral"),
    (" acrylate", [], "neutral"),
    (" propylene glycol", ["dry"], "good"),
    (" pentylene glycol", ["dry"], "good"),
    (" butylene glycol", ["dry"], "good"),
    (" caprylic", ["oily"], "good"),
    (" zinc oxide", ["sensitive"], "good"),
    (" titanium dioxide", ["sensitive"], "good"),
    (" mica", [], "neutral"),
    (" talc", [], "neutral"),
)


def infer_from_name_only(norm_ing: str) -> dict | None:
    """If ingredient name matches a simple rule, return a low-confidence entry."""
    if not norm_ing or len(norm_ing) < 3:
        return None
    for suffix_or_pattern, skin_types, effect in NAME_BASED_RULES:
        if suffix_or_pattern in norm_ing:
            return {
                "skin_types": list(skin_types),
                "effect": effect,
                "confidence": "low",
            }
    return None


def build_inferred_map(use_name_rules: bool = True) -> dict:
    skin_map = load_skin_map()
    missing = get_missing_ingredients(skin_map)
    # Only keys that have usable data; sort by length desc to match longest first
    map_keys_sorted = sorted(
        [
            k for k in skin_map.keys()
            if _entry_to_inferred(skin_map.get(k)) is not None
        ],
        key=lambda x: -len(_normalize(x)),
    )
    inferred = {}
    missing_list = list(missing)
    for i, ing in enumerate(missing_list):
        if (i + 1) % 500 == 0:
            print(f"  progress: {i + 1}/{len(missing_list)}")
        norm_missing = _normalize(ing)
        entry = infer_from_substring(norm_missing, map_keys_sorted, skin_map)
        if not entry and use_name_rules:
            entry = infer_from_name_only(norm_missing)
        if entry:
            inferred[ing] = entry
    return inferred, missing


def export_missing_to_csv(missing_ingredients: set, inferred_keys: set) -> int:
    """
    Write still-missing ingredients to CSV for manual/rule-fill curation.
    - Drop list: symbols, sentence fragments, package/material, tech/complex-only -> excluded.
    - % pattern: strip to ingredient name only; optional strength_hint column.
    - Only export real ingredient candidates (min length, has letters).
    Columns: ingredient, skin_type, effect, confidence [, strength_hint].
    """
    still_missing = missing_ingredients - inferred_keys
    # Normalize with % strip and collect (normalized_name, strength_hint, original for first occurrence)
    seen_norm = set()
    rows = []
    for ing in sorted(still_missing):
        if should_drop_ingredient(ing):
            continue
        name_norm, strength = strip_percent_and_strength(ing)
        if not name_norm or not is_real_ingredient_candidate(name_norm):
            continue
        if name_norm in seen_norm:
            continue
        seen_norm.add(name_norm)
        # Export normalized name so curation is on canonical form
        rows.append((name_norm, strength))
    if not rows:
        return 0
    with open(MISSING_FOR_CURATION_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ingredient", "skin_type", "effect", "confidence", "strength_hint"])
        for name_norm, strength in rows:
            w.writerow([name_norm, "", "", "", strength or ""])
    return len(rows)


def merge_inferred_into_skin_map() -> int:
    """Merge inferred_ingredient_skin_map.json into ingredient_skin_map.json. Returns count added."""
    if not INFERRED_OUTPUT_PATH.exists():
        print("Run without --merge first to create inferred_ingredient_skin_map.json")
        return 0
    with open(INFERRED_OUTPUT_PATH, encoding="utf-8") as f:
        inferred = json.load(f)
    with open(INGREDIENT_SKIN_MAP_PATH, encoding="utf-8") as f:
        current = json.load(f)
    added = 0
    for k, v in inferred.items():
        if k not in current:
            current[k] = v
            added += 1
    with open(INGREDIENT_SKIN_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return added


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true", help="Merge inferred into ingredient_skin_map.json")
    ap.add_argument("--export-missing", action="store_true", help="Export still-missing ingredients to CSV for manual/rule-fill curation")
    ap.add_argument("--no-name-rules", action="store_true", help="Only use substring propagation, no name-based rules")
    args = ap.parse_args()

    if args.merge:
        n = merge_inferred_into_skin_map()
        print(f"Merged {n} inferred entries into ingredient_skin_map.json")
        return

    print("Collecting missing ingredients and inferring (substring + name rules)...")
    inferred, missing = build_inferred_map(use_name_rules=not args.no_name_rules)
    with open(INFERRED_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(inferred, f, ensure_ascii=False, indent=2)
    print(f"Inferred {len(inferred)} entries -> {INFERRED_OUTPUT_PATH.name}")
    print("Run with --merge to add them to ingredient_skin_map.json")

    still_count = len(missing) - len(inferred)
    print(f"Still missing (no match): {still_count}")

    if args.export_missing:
        n = export_missing_to_csv(missing, set(inferred.keys()))
        print(f"Exported {n} still-missing ingredients -> {MISSING_FOR_CURATION_PATH.name}")
        print("  Fill skin_type (comma-separated), effect (good/avoid/neutral), confidence (high/medium/low), then run build_ingredient_skin_map.py")


if __name__ == "__main__":
    main()
