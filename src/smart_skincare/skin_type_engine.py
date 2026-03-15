"""
6 skin types: dry, normal, oily, pigmentation, sensitive, wrinkle
- Ingredient -> 6-type fit (Paula benefits/functions + INCI Decoder what_it_does/details keywords)
- User inputs -> 6-type profile (weights)
- Product score = ingredient x type matching + rating
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"
CACHE_DIR = ROOT / "cache"
INGREDIENT_6TYPES_PATH = CACHE_DIR / "ingredient_6types.json"  # norm -> [dry, oily, ...] fit types

# Per-type keywords (if present in benefits / what_it_does / details text, type is "fit")
KEYWORDS_FOR_TYPE = {
    "dry": [
        "hydration", "hydrat", "moisturiz", "moisturising", "humectant", "skin-identical",
        "emollient", "barrier", "dry skin", "anti-dry", "water-binding", "hyaluronic",
        "glycerin", "urea", "ceramide", "squalane", "repair",
    ],
    "normal": [
        "balance", "normal skin", "gentle", "skin conditioning",
    ],
    "oily": [
        "oil", "sebum", "matte", "absorb", "pore", "acne", "anti-acne", "astringent",
        "oil-control", "oil-free", "exfoliant", "bha", "salicylic", "niacinamide",
    ],
    "pigmentation": [
        "brighten", "whiten", "dark spot", "pigment", "tone", "even", "vitamin c",
        "ascorb", "arbutin", "kojic", "tranexamic", "niacinamide", "evens skin tone",
    ],
    "sensitive": [
        "soothing", "calm", "sensitive", "anti-inflammatory", "anti-irritat",
        "barrier", "centella", "chamomile", "allantoin", "bisabolol", "oat",
    ],
    "wrinkle": [
        "anti-aging", "anti-age", "wrinkle", "firm", "peptide", "retinol", "retinoid",
        "collagen", "elastin", "glycolic", "lactic", "aha", "vitamin a", "resveratrol",
    ],
}


def normalize_ingredient(name: str) -> str:
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def paula_canonicalize(name: str) -> str:
    """STEP 1: lower, remove parentheses, remove periods, normalize space (match Paula reference)."""
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _text_matches_types(text: str) -> list:
    """Search text for keywords -> return list of matching 6 types."""
    if not text:
        return []
    text = text.lower()
    matched = []
    for skin_type, keywords in KEYWORDS_FOR_TYPE.items():
        for kw in keywords:
            if kw.lower() in text:
                matched.append(skin_type)
                break
    return list(dict.fromkeys(matched))  # Preserve order, dedupe


def build_ingredient_to_6types(save_path: Path = None) -> dict:
    """
    Build per-ingredient fit 6-type list from Paula benefits/functions
    and ingredient_info_incidecoder.json (165).
    """
    save_path = save_path or INGREDIENT_6TYPES_PATH
    out = defaultdict(list)

    # 1) Paula
    path = DATA_DIR / "Paula_embedding_SUMLIST_before_422.csv"
    if not path.exists():
        path = DATA_DIR / "Paula_SUM_LIST.csv"
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = paula_canonicalize(row.get("ingredient_name", ""))
                if not name:
                    continue
                benefits = row.get("benefits", "") or ""
                functions = row.get("functions", "") or ""
                text = benefits + " " + functions
                types = _text_matches_types(text)
                if types:
                    existing = set(out.get(name, []))
                    for t in types:
                        existing.add(t)
                    out[name] = list(existing)

    # 2) INCI Decoder (165)
    path_id = CACHE_DIR / "ingredient_info_incidecoder.json"
    if path_id.exists():
        with open(path_id, encoding="utf-8") as f:
            id_data = json.load(f)
        for name, info in id_data.items():
            text = " ".join(info.get("what_it_does", [])) + " " + (info.get("details") or "")
            types = _text_matches_types(text)
            if types:
                existing = set(out.get(name, []))
                for t in types:
                    existing.add(t)
                out[name] = list(existing)

    result = dict(out)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def user_input_to_profile(
    hydration_level: str = "normal",  # low / normal / high
    oil_level: str = "normal",        # low / normal / high
    sensitivity: str = "normal",      # low / normal / high
    age: int = None,
    concerns: list = None,            # ["dryness", "wrinkles", "pigmentation"]
    region: str = None,
) -> dict:
    """
    User inputs -> 6-type weights (0-1). Combinable.
    """
    profile = {t: 0.0 for t in KEYWORDS_FOR_TYPE}
    # dry
    if hydration_level == "low" or (concerns and "dryness" in concerns):
        profile["dry"] = max(profile["dry"], 0.9)
    elif hydration_level == "normal":
        profile["dry"] = 0.3
    # oily
    if oil_level == "high":
        profile["oily"] = 0.9
    elif oil_level == "normal":
        profile["oily"] = 0.3
    # sensitive
    if sensitivity == "high":
        profile["sensitive"] = 0.9
    elif sensitivity == "normal":
        profile["sensitive"] = 0.2
    # pigmentation
    if concerns and "pigmentation" in concerns:
        profile["pigmentation"] = 0.9
    # wrinkle
    if (age is not None and age >= 35) or (concerns and "wrinkles" in concerns):
        profile["wrinkle"] = 0.9
    # normal: default
    profile["normal"] = 0.5
    return profile


def score_product(
    ingredient_list: list,
    user_profile: dict,
    ingredient_to_6types: dict,
    normalize_fn=None,
) -> float:
    """
    Product score: higher when product ingredients match user profile (6 types).
    score = sum over (user_profile weight for each type the ingredient fits)
    """
    normalize_fn = normalize_fn or normalize_ingredient
    total = 0.0
    count = 0
    for ing in ingredient_list:
        norm = normalize_fn(ing)
        types = ingredient_to_6types.get(norm, [])
        for t in types:
            total += user_profile.get(t, 0)
        if types:
            count += 1
    if count == 0:
        return 0.0
    return total / max(count, 1)  # Average fit


def load_ingredient_6types() -> dict:
    if INGREDIENT_6TYPES_PATH.exists():
        with open(INGREDIENT_6TYPES_PATH, encoding="utf-8") as f:
            return json.load(f)
    return build_ingredient_to_6types()


if __name__ == "__main__":
    print("Building ingredient -> 6 types from Paula + INCI Decoder (165)...")
    m = build_ingredient_to_6types()
    print(f"  Mapped ingredients: {len(m)}")
    # sample
    for k, v in list(m.items())[:5]:
        print(f"    {k[:40]:40} -> {v}")
    print("\nUser profile sample (dryness + wrinkles concern):")
    p = user_input_to_profile(hydration_level="low", concerns=["wrinkles"])
    print("  ", p)
    print("\nDone. See", INGREDIENT_6TYPES_PATH.name)
