"""
STEP 5 — Build ingredient -> 6 types + effect + confidence (ingredient_skin_map.json).
- Base: ingredient_6types.json (from Paula + INCI) -> effect=good, confidence=medium
- Merge: manual_curation.csv, missing_ingredients_for_curation.csv, filled_latin_v2.csv, inferred, manual
  skin_type: comma-separated (dry,normal,oily,pigmentation,sensitive,wrinkle). effect: good|avoid|neutral.
  confidence: high|medium|low only (no float; default low). Rows with both skin_type and effect empty are skipped.
"""
import csv
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
INGREDIENT_6TYPES_PATH = CACHE_DIR / "ingredient_6types.json"
MANUAL_CURATION_PATH = DATA_DIR / "manual_curation.csv"
MISSING_FOR_CURATION_PATH = DATA_DIR / "missing_ingredients_for_curation.csv"
FILLED_LATIN_V2_PATH = DATA_DIR / "filled_latin_v2.csv"
WITHSEARCH_FILLED_V2_PATH = DATA_DIR / "withSearch_filled_v2.csv"
WITHSEARCH_FILLED_REMAINING_PATH = DATA_DIR / "withSearch_filled_remaining.csv"
INFERRED_SKIN_MAP_PATH = CACHE_DIR / "inferred_ingredient_skin_map.json"
OUTPUT_PATH = CACHE_DIR / "ingredient_skin_map.json"

SKIN_TYPES = {"dry", "normal", "oily", "pigmentation", "sensitive", "wrinkle"}
SKIN_TYPE_ORDER = ["dry", "normal", "oily", "pigmentation", "sensitive", "wrinkle"]
EFFECTS = {"good", "avoid", "neutral"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}


def _normalize(s: str) -> str:
    if not s:
        return ""
    return s.strip().lower()


def _sort_skin_types(types: list) -> list:
    """Return list in fixed order for consistent aggregation."""
    if not types:
        return []
    return [t for t in SKIN_TYPE_ORDER if t in types]


def load_6types() -> dict:
    """ingredient -> list of skin types."""
    if not INGREDIENT_6TYPES_PATH.exists():
        return {}
    with open(INGREDIENT_6TYPES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_curation_csv(path: Path) -> dict:
    """ingredient -> { skin_types: list, effect, confidence }. Skips rows with empty skin_type and effect (unfilled template)."""
    out = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ing = _normalize(row.get("ingredient", ""))
            if not ing:
                continue
            st = (row.get("skin_type") or "").strip()
            effect = (row.get("effect") or "").strip().lower()
            # Skip unfilled template rows (no skin_type and no effect)
            if not st and not effect:
                continue
            types = [t.strip().lower() for t in st.split(",") if t.strip() and t.strip().lower() in SKIN_TYPES]
            types = _sort_skin_types(types)
            effect = effect or "neutral"
            if effect not in EFFECTS:
                effect = "neutral"
            confidence = (row.get("confidence") or "").strip().lower() or "low"
            if confidence not in CONFIDENCE_LEVELS:
                confidence = "low"
            out[ing] = {
                "skin_types": types,
                "effect": effect,
                "confidence": confidence,
            }
    return out


def load_manual_curation() -> dict:
    return _load_curation_csv(MANUAL_CURATION_PATH)


def load_missing_for_curation() -> dict:
    """Same format as manual_curation; from fill_missing_ingredient_data.py --export-missing (after you fill it)."""
    return _load_curation_csv(MISSING_FOR_CURATION_PATH)


def load_filled_latin_v2() -> dict:
    """Latin+extract/oil from apply_curation_rules_v2.py (confidence=low). Same schema as manual."""
    return _load_curation_csv(FILLED_LATIN_V2_PATH)


def load_withSearch_filled_v2() -> dict:
    """Rule-filled needs_human_filtered_v2 from fill_needs_human_withSearch.py. Same schema as manual."""
    return _load_curation_csv(WITHSEARCH_FILLED_V2_PATH)


def load_withSearch_filled_remaining() -> dict:
    """Rule-filled remaining (in products, not in map) from fill_remaining_not_in_map.py."""
    return _load_curation_csv(WITHSEARCH_FILLED_REMAINING_PATH)


def load_inferred_skin_map() -> dict:
    """inferred_ingredient_skin_map.json from fill_missing_ingredient_data.py (substring + name rules)."""
    if not INFERRED_SKIN_MAP_PATH.exists():
        return {}
    with open(INFERRED_SKIN_MAP_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for ing, v in raw.items():
        if not ing or not isinstance(v, dict):
            continue
        types = [t for t in (v.get("skin_types") or []) if t in SKIN_TYPES]
        types = _sort_skin_types(types)
        effect = (v.get("effect") or "good").strip().lower()
        if effect not in EFFECTS:
            effect = "good"
        confidence = (v.get("confidence") or "low").strip().lower()
        if confidence not in CONFIDENCE_LEVELS:
            confidence = "low"
        out[ing.strip().lower()] = {"skin_types": types, "effect": effect, "confidence": confidence}
    return out


def load_existing_skin_map() -> dict:
    """Current ingredient_skin_map.json if it exists (so we don't drop previously merged inferred)."""
    if not OUTPUT_PATH.exists():
        return {}
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for ing, v in raw.items():
        if not ing:
            continue
        ing = ing.strip().lower()
        if isinstance(v, list):
            types = _sort_skin_types([t for t in v if t in SKIN_TYPES])
            out[ing] = {"skin_types": types, "effect": "good", "confidence": "medium"}
        elif isinstance(v, dict):
            types = _sort_skin_types([t for t in (v.get("skin_types") or []) if t in SKIN_TYPES])
            effect = (v.get("effect") or "good").strip().lower()
            if effect not in EFFECTS:
                effect = "good"
            confidence = (v.get("confidence") or "low").strip().lower()
            if confidence not in CONFIDENCE_LEVELS:
                confidence = "low"
            out[ing] = {"skin_types": types, "effect": effect, "confidence": confidence}
    return out


def build_ingredient_skin_map() -> dict:
    """Merge existing map + ingredient_6types + inferred + missing_ingredients_for_curation + manual_curation. Each entry: { skin_types, effect, confidence }."""
    merged = load_existing_skin_map()
    base = load_6types()
    manual = load_manual_curation()
    missing_curation = load_missing_for_curation()
    filled_latin_v2 = load_filled_latin_v2()
    withSearch_filled_v2 = load_withSearch_filled_v2()
    withSearch_filled_remaining = load_withSearch_filled_remaining()
    inferred = load_inferred_skin_map()
    # Add from 6types where not already present
    for ing, types in base.items():
        types = [t for t in types if t in SKIN_TYPES]
        types = _sort_skin_types(types)
        if types and ing not in merged:
            merged[ing] = {"skin_types": types, "effect": "good", "confidence": "medium"}
    # Inferred (substring + name rules)
    for ing, data in inferred.items():
        merged[ing] = {"skin_types": data["skin_types"], "effect": data["effect"], "confidence": data["confidence"]}
    # Missing-for-curation (filled CSV)
    for ing, data in missing_curation.items():
        merged[ing] = {"skin_types": data["skin_types"], "effect": data["effect"], "confidence": data["confidence"]}
    # Filled Latin v2 (Latin+extract/oil, low confidence)
    for ing, data in filled_latin_v2.items():
        merged[ing] = {"skin_types": data["skin_types"], "effect": data["effect"], "confidence": data["confidence"]}
    # withSearch-filled v2 (fill_needs_human_withSearch.py)
    for ing, data in withSearch_filled_v2.items():
        merged[ing] = {"skin_types": data["skin_types"], "effect": data["effect"], "confidence": data["confidence"]}
    # withSearch-filled remaining (fill_remaining_not_in_map.py)
    for ing, data in withSearch_filled_remaining.items():
        merged[ing] = {"skin_types": data["skin_types"], "effect": data["effect"], "confidence": data["confidence"]}
    # Manual (highest priority)
    for ing, data in manual.items():
        merged[ing] = {"skin_types": data["skin_types"], "effect": data["effect"], "confidence": data["confidence"]}
    result = dict(merged)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


if __name__ == "__main__":
    m = build_ingredient_skin_map()
    print(f"ingredient_skin_map: {len(m)} ingredients -> {OUTPUT_PATH.name}")
    for k, v in list(m.items())[:6]:
        print(f"  {k[:40]:40} -> types={v['skin_types']}, effect={v['effect']}, conf={v['confidence']}")
