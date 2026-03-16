"""
STEP 6 — MVP recommendation: score products, Top 10, 3 key ingredients.
- score += user_profile weight for each ingredient in skin_map
- score -= weight if Paula rating == POOR
- Return top N products + why (top 3 contributing ingredients)
"""
import csv
import math
import re
import json
from pathlib import Path
from collections import defaultdict
from categorize_products import categorize

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"
CACHE_DIR = ROOT / "cache"

INGREDIENT_SKIN_MAP_PATH = CACHE_DIR / "ingredient_skin_map.json"
PAULA_CSV = DATA_DIR / "Paula_embedding_SUMLIST_before_422.csv"
PAULA_CSV_ALT = DATA_DIR / "Paula_SUM_LIST.csv"
FINAL_DATA_CSV = DATA_DIR / "Filltered_combined_data.csv"
REVIEW_STATS_PATH = CACHE_DIR / "review_stats.json"

# effect: good -> +score, avoid -> -score, neutral -> 0. Not in map -> neutral (0).
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}
AVOID_PENALTY = 2.5  # subtract per avoid ingredient (stronger so fragrance/irritants drop rank)
POOR_RATING_PENALTY = 1.0  # extra subtract when Paula rating == POOR
RATING_WEIGHT = 0.3  # product score += rating * RATING_WEIGHT (stronger so rating breaks ties)
BASE_WEIGHT = 0.6    # final_score = BASE_WEIGHT * base_score + REVIEW_WEIGHT * review_score
REVIEW_WEIGHT = 0.4  # 6:4 ratio (base : review)

# concern (wrinkle, pigmentation) stronger than base (dry); normal/oily base = 0 so no spill
TYPE_MULT = {
    "dry": 0.8,
    "normal": 0.2,   # weak so not every ingredient counts as normal
    "oily": 1.0,     # need >= 1 so oily recommendations are meaningful
    "pigmentation": 2.0,
    "sensitive": 1.2,
    "wrinkle": 3.0,
}

# active vs base: active (retinol, peptide, etc.) gets higher weight so they beat base-heavy products
TIER_MULT = {"active": 2.5, "base": 1.0, "other": 0.6}
DRY_CAP = 12.0
WRINKLE_CAP = 20.0

# --- Score improvements: normalization, active saturation, sensitive penalty, set/kit ---
# Normalization only when n_ing > this (so 10–35 ing products keep full score, like before)
NORM_APPLY_ABOVE = 40
# Active (wrinkle/pigmentation) diminishing returns: A_max * tanh(sum_active / tau); higher TAU = gentler cap
ACTIVE_SATURATION_TAU = 7.0
ACTIVE_SATURATION_A_MAX = 22.0
# Sensitive/dry penalty for actives
SENSITIVE_AHA_PENALTY = 1.5   # AHA present + (sensitive or very dry)
SENSITIVE_LAA_PENALTY = 1.0    # L-AA (ascorbic) present + sensitive
# Set/kit: name keywords or ingredient count threshold → stronger normalization
KIT_NAME_KEYWORDS = ("set", "kit", "trio", "mini", "the littles")
KIT_INGREDIENT_THRESHOLD = 80  # above this → treat as kit (stronger norm)
# Marketing / non-INCI tokens → contribute 0 to score
MARKETING_NO_SCORE_KEYWORDS = (
    "complex", "technology", "system", "blend", "proprietary", "patent", "division",
)

# Oily = sebum/pore focus: suppress retinoid/emollient contribution in score (ranking as well as drivers)
OILY_SUPPRESS_FAMILIES = ("retinoid", "emollient")
OILY_SUPPRESS_MULT = 0.2  # Applied only to oily bucket

# Type -> allowed families for key-ingredient display (so explanation fits the type)
TYPE_FAMILY_ALLOW = {
    "dry": ["humectant", "barrier", "emollient"],
    "oily": ["aha_bha", "sebum_control"],
    "pigmentation": ["antioxidant", "aha_bha", "other"],
    "wrinkle": ["retinoid", "peptide", "aha_bha", "antioxidant"],
    "sensitive": ["humectant", "barrier", "other"],
    "normal": ["humectant", "barrier", "emollient"],
}

# Fallback: family-based entry when ingredient not in skin_map. Weakened vs knowledge-base.
FALLBACK_WEIGHT_MULT = 0.7  # option 1: weight *= this when source=="fallback_family"
AVOID_FALLBACK_KEYWORDS = (
    "fragrance", "parfum", "perfume", "limonene", "linalool", "citral", "geraniol", "eugenol",
    "denat", "alcohol denat", "menthol", "camphor")

# Token-level: filter out "not an ingredient" (INCI usually 3-6 words, under 60 chars)
TOKEN_MAX_LEN = 60
TOKEN_MAX_WORDS = 8
TOKEN_SENTENCE_MARKERS = (":", "™", "®", "http", "www", " - ", "—")
TOKEN_UNIT_MARKERS = (" mg", " ml", "mg ", "ml ")  # % excluded: strip "20%" and keep ingredient name
TOKEN_MARKETING_KEYWORDS = (
    "detox", "brighten", "helps", "clinically", "anti-aging", "reduces", "for all skin",
    "exfoliates", "tones", "clears", "fighting", "lightens", "reduces the look", "step 1", "step 2")
# Raw string: detect non-ingredient description text
RAW_MIN_COMMAS = 3
RAW_SUSPICIOUS_LEN = 80
RAW_PUNCT_RATIO_THRESH = 0.05  # Ratio of : . ! ?
STRICT_MAX_LEN = 40
STRICT_MAX_WORDS = 5

# Raw text classification: skip parsing and exclude from recommendation
NO_INGREDIENTS_DISCLAIMER_PHRASES = (
    "ingredient list is subject to change",
    "take the quiz",
    "to view your formulations",
    "may differ from packaging",
    "skin genome quiz",
)
DYNAMIC_FORMULA_PHRASES = (
    "based on quiz", "ingredients will be based", "your formulations",
    "personalized set", "personalized formula",
)
NON_COSMETIC_MATERIAL_KEYWORDS = (
    "momme", "thread count", "long-fiber mulberry silk",
    "100% high-grade", "mulberry silk", "silk pillowcase", "pillowcase",
)
# Latin name variants for INCI matching (raw text replace before substring match)
LATIN_RAW_REPLACEMENTS = (
    ("jasmine officinale", "jasminum officinale"),
)


def _has_inci_like_pattern(raw: str) -> bool:
    """True if raw looks like an ingredient list (many commas + e.g. Latin/paren pattern)."""
    if not raw or raw.count(",") < 4:
        return False
    # INCI often has "Rosa Canina (Rosehip)" or "Simmondsia Chinensis (Jojoba)"
    if re.search(r"\w+\s*\([^)]+\)", raw):
        return True
    low = raw.lower()
    if "seed oil" in low or " extract" in low or " leaf " in low:
        return True
    return False


def _raw_ingredients_classification(raw: str) -> dict:
    """
    Classify raw text: if disclaimer (and not INCI), dynamic formula, or material, do not parse.
    Returns {"use_parser": True} or {"use_parser": False, "reason": "..."}.
    """
    if not raw or not isinstance(raw, str):
        return {"use_parser": True}
    low = raw.strip().lower()
    comma_count = raw.count(",")
    for phrase in DYNAMIC_FORMULA_PHRASES:
        if phrase in low:
            return {"use_parser": False, "reason": "dynamic_formula"}
    for phrase in NO_INGREDIENTS_DISCLAIMER_PHRASES:
        if phrase in low:
            # Only treat as disclaimer when whole text is disclaimer; INCI list with disclaimer sentence → parse
            if _has_inci_like_pattern(raw):
                break
            return {"use_parser": False, "reason": "no_ingredients_disclaimer"}
    for kw in NON_COSMETIC_MATERIAL_KEYWORDS:
        if kw in low:
            return {"use_parser": False, "reason": "non_cosmetic_material"}
    # No no_ingredients_marketing_text here: always try parse; 2-pass in parser + no_inci_provided after if still empty
    return {"use_parser": True}


def top_types(user_profile: dict, k: int = 2, min_w: float = 0.1) -> list:
    """Top k types by profile weight (for dynamic key-driver display)."""
    items = [(t, w) for t, w in (user_profile or {}).items() if w >= min_w]
    items.sort(key=lambda x: -x[1])
    return [t for t, _ in items[:k]]


def _normalize(name: str) -> str:
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def load_ingredient_skin_map() -> dict:
    """Returns ingredient -> { skin_types: list, effect: good|avoid|neutral, confidence: high|medium|low }.
    Backward compat: if value is a list, treat as { skin_types: value, effect: good, confidence: medium }.
    """
    raw = {}
    if INGREDIENT_SKIN_MAP_PATH.exists():
        with open(INGREDIENT_SKIN_MAP_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        p = CACHE_DIR / "ingredient_6types.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                raw = json.load(f)
    out = {}
    for ing, v in raw.items():
        if isinstance(v, list):
            out[ing] = {"skin_types": v, "effect": "good", "confidence": "medium"}
        else:
            types = v.get("skin_types", [])
            effect = (v.get("effect") or "neutral").strip().lower()
            if effect not in ("good", "avoid", "neutral"):
                effect = "neutral"
            conf = (v.get("confidence") or "low").strip().lower()
            if conf not in ("high", "medium", "low"):
                conf = "low"
            out[ing] = {"skin_types": types, "effect": effect, "confidence": conf}
    return out


def load_review_stats() -> dict:
    """Load review stats cache: {normalized_product_name: {review_score, avg, count, recentness}}."""
    if not REVIEW_STATS_PATH.exists():
        return {}
    try:
        with open(REVIEW_STATS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _strength_bonus_by_index(idx: int) -> float:
    """INCI order proxy: earlier ingredients are more likely higher concentration."""
    if idx <= 4:
        return 0.25
    if idx <= 14:
        return 0.12
    return 0.05


def _apply_inci_strength_bonus(bucket: dict, ingredient_list: list, user_profile: dict):
    """
    Add a small bonus to type buckets if allowed-family actives appear early in the INCI list.
    This is a proxy for concentration (% not available).
    """
    if not ingredient_list:
        return
    # Determine which types matter for this user (avoid spilling)
    primary = top_types(user_profile, k=2, min_w=0.1)
    if not primary:
        return
    for idx, ing in enumerate(ingredient_list):
        if not ing or _should_drop_ingredient_token(ing):
            continue
        fam = _ingredient_family(ing)
        bonus = _strength_bonus_by_index(idx)
        for t in primary:
            allowed = set(TYPE_FAMILY_ALLOW.get(t) or [])
            if not allowed:
                continue
            # Only apply when the ingredient family is meaningful for this type
            if fam in allowed:
                bucket[t] = bucket.get(t, 0.0) + user_profile.get(t, 0.0) * bonus


def _paula_canonicalize(name: str) -> str:
    """Match STEP 1: lower, remove parentheses, remove periods, normalize space."""
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_paula_rating_map() -> dict:
    """ingredient (Paula canonical) -> rating string (best, good, average, poor, rest)."""
    path = PAULA_CSV if PAULA_CSV.exists() else PAULA_CSV_ALT
    out = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = _paula_canonicalize(row.get("ingredient_name", ""))
            r = (row.get("rating") or "").strip().lower()
            if name:
                out[name] = r
    return out


def _canonicalize_ingredient(name: str) -> str:
    """Use alias table if available so product ingredients match skin_map keys."""
    try:
        from ingredient_canonical import canonicalize_ingredient
        return canonicalize_ingredient(name) or _normalize(name)
    except Exception:
        return _normalize(name)


def _is_marketing_no_score_ingredient(ing: str) -> bool:
    """True if ingredient name looks like marketing/non-INCI → contribute 0 to score."""
    if not ing or not isinstance(ing, str):
        return True
    low = (ing or "").strip().lower()
    return any(kw in low for kw in MARKETING_NO_SCORE_KEYWORDS)


def _should_drop_ingredient_token(s: str, strict: bool = False) -> bool:
    """True if token looks like description/marketing, not INCI. strict=True for suspicious raw strings."""
    if not s or not isinstance(s, str):
        return True
    t = s.strip()
    # If parenthetical is too long, remove and re-evaluate
    if "(" in t and ")" in t:
        t = re.sub(r"\([^)]{30,}\)", "", t).strip()
    if not t:
        return True
    low = t.lower()
    max_len = STRICT_MAX_LEN if strict else TOKEN_MAX_LEN
    max_words = STRICT_MAX_WORDS if strict else TOKEN_MAX_WORDS
    if len(t) > max_len or len(t.split()) > max_words:
        return True
    if any(m in t for m in TOKEN_SENTENCE_MARKERS):
        return True
    if any(m in low for m in TOKEN_UNIT_MARKERS):
        return True
    if any(kw in low for kw in TOKEN_MARKETING_KEYWORDS):
        return True
    return False


_KNOWN_INGREDIENT_SET_CACHE = None


def _load_known_ingredient_set(min_len: int = 5) -> set:
    """Paula ingredient_name + skin_map keys, normalized (for substring fallback)."""
    global _KNOWN_INGREDIENT_SET_CACHE
    if _KNOWN_INGREDIENT_SET_CACHE is not None:
        return _KNOWN_INGREDIENT_SET_CACHE
    known = set()
    path = PAULA_CSV if PAULA_CSV.exists() else PAULA_CSV_ALT
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                n = _paula_canonicalize(row.get("ingredient_name", ""))
                if n and len(n) >= min_len:
                    known.add(n)
    if INGREDIENT_SKIN_MAP_PATH.exists():
        with open(INGREDIENT_SKIN_MAP_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for k in (data if isinstance(data, dict) else {}):
            n = _paula_canonicalize(k)
            if n and len(n) >= min_len:
                known.add(n)
    _KNOWN_INGREDIENT_SET_CACHE = known
    return known


def _apply_latin_expansion_to_raw(raw: str) -> str:
    """Replace Latin variants in raw so substring match can find INCI (e.g. jasmine officinale -> jasminum)."""
    s = raw
    for old, new in LATIN_RAW_REPLACEMENTS:
        s = re.sub(re.escape(old), new, s, flags=re.I)
    return s


def _strip_colon_bullet_blocks(raw: str) -> str:
    """Remove '- X: description' blocks so remainder can be parsed as comma-separated ingredient list (2-pass)."""
    if not raw or ":" not in raw:
        return raw
    # Remove each " - X: ... " until next bullet " - ", or ". Cap" / ", Cap" (start of ingredient list), or end
    out = re.sub(r"\s*-\s*[^:]+:\s*.*?(?=\s+-\s+|\.\s+[A-Z\(]|,\s*[A-Z\(]|$)", " ", raw, flags=re.DOTALL)
    return re.sub(r"\s+", " ", out).strip()


def _looks_like_marketing_only(raw: str) -> bool:
    """True when raw has few commas and sentence/marketing keywords (no real INCI list)."""
    if not raw or not isinstance(raw, str):
        return False
    low = raw.strip().lower()
    if raw.count(",") >= RAW_MIN_COMMAS or len(low) <= 40:
        return False
    return any(m in low for m in TOKEN_SENTENCE_MARKERS) or any(kw in low for kw in TOKEN_MARKETING_KEYWORDS)


def _extract_ingredients_by_substring(raw: str, known: set) -> list:
    """Find known ingredients that appear as substring in raw. Prefer longer matches."""
    if not raw or not known:
        return []
    raw = _apply_latin_expansion_to_raw(raw)
    raw_norm = _normalize(raw)
    found = [ing for ing in known if ing in raw_norm]
    found.sort(key=len, reverse=True)
    keep = []
    for ing in found:
        if any(ing in other for other in keep):
            continue
        keep.append(ing)
    return keep


def _parse_ingredients(raw: str) -> list:
    """Parse cosmetics Ingredients column into list of canonical names (unique, order preserved)."""
    if not raw or not isinstance(raw, str):
        return []
    # Strip (100%) from raw so it doesn't break matching
    raw = re.sub(r"\s*\(\s*100\s*%\s*\)", "", raw, flags=re.I)
    # Remove "Active Ingredients:" / "Inactive Ingredients:" headers so they aren't parsed as tokens
    raw = re.sub(r"(?i)active\s+ingredients\s*:\s*", "", raw)
    raw = re.sub(r"(?i)inactive\s+ingredients\s*:\s*", "", raw)
    # Line-level: detect "this line is not an ingredient list"
    comma_count = raw.count(",")
    punct_count = sum(raw.count(c) for c in ":.!?")
    strict = False
    if comma_count < RAW_MIN_COMMAS and len(raw) > RAW_SUSPICIOUS_LEN:
        strict = True
    if len(raw) > 0 and (punct_count / len(raw)) > RAW_PUNCT_RATIO_THRESH:
        strict = True
    try:
        from ingredient_cleaning import clean_raw_ingredient
    except Exception:
        clean_raw_ingredient = None
    def _strip_trailing_percent(s: str) -> str:
        """Remove trailing ' 20%' etc so SPF-style 'Zinc Oxide 20%' keeps ingredient name."""
        return re.sub(r"\s+\d+\s*%\s*$", "", s, flags=re.I).strip()

    def _strip_leading_percent(s: str) -> str:
        """Remove leading '3% ' etc so '3% TXA' -> 'TXA' for canonicalize/alias."""
        return re.sub(r"^\d+(?:\.\d+)?\s*%\s*", "", s, flags=re.I).strip()

    if clean_raw_ingredient:
        cleaned = [_normalize(_strip_leading_percent(_strip_trailing_percent(str(x).strip()))) for x in clean_raw_ingredient(raw) if str(x).strip()]
        cleaned = [c for c in cleaned if c and len(c) > 2]
    else:
        parts = [p.strip() for p in re.split(r",\s*(?=[A-Z\(])", raw) if p.strip()]
        parts = [_strip_leading_percent(_strip_trailing_percent(p)) for p in parts]
        cleaned = [_normalize(x) for x in parts if _normalize(x) and len(_normalize(x)) > 2]
    # Colon-prefix: "X: description" or "- X: description" -> take X only (merge with cleaned)
    for seg in re.split(r"[,.]\s*", raw):
        m = re.match(r"^\s*\-?\s*(.+?)\s*:\s*", seg.strip())
        if m:
            pre = _strip_leading_percent(_strip_trailing_percent(m.group(1).strip().strip("- ")))
            if pre and len(pre) > 2:
                n = _normalize(pre)
                if n and n not in (c for c in cleaned):
                    cleaned.append(n)
    # When raw has no/few commas, try taking text before first ":" as ingredient (e.g. Sephora "-Squalane: Supports...")
    if not cleaned and raw.strip() and comma_count < 2:
        first = _strip_leading_percent(_strip_trailing_percent(raw.split(":")[0].strip().strip("- ")))
        if first and len(first) > 2:
            cleaned = [_normalize(first)]
    parsed = [_canonicalize_ingredient(x) for x in cleaned]
    seen = set()
    uniq = []
    for ing in parsed:
        if not ing:
            continue
        if _should_drop_ingredient_token(ing, strict=strict):
            # Recover "100% ingredient name" by stripping leading N%
            ing_stripped = re.sub(r"^\d+%\s*", "", ing, flags=re.I).strip()
            if ing_stripped and not _should_drop_ingredient_token(ing_stripped, strict=strict):
                ing = _canonicalize_ingredient(ing_stripped)
            else:
                continue
        if ing not in seen:
            seen.add(ing)
            uniq.append(ing)
    # INCI substring fallback when parse returned empty but raw has content
    if not uniq and raw.strip():
        known = _load_known_ingredient_set(min_len=5)
        fallback = _extract_ingredients_by_substring(raw, known)
        for ing in fallback:
            ing_can = _canonicalize_ingredient(ing)
            if ing_can and ing_can not in seen and not _should_drop_ingredient_token(ing_can, strict=strict):
                seen.add(ing_can)
                uniq.append(ing_can)
    # 2-pass: if still empty and raw has bullet " - X: desc ", strip those and parse remainder as comma list
    if not uniq and raw.strip() and " - " in raw and ":" in raw:
        stripped = _strip_colon_bullet_blocks(raw)
        if stripped and stripped != raw:
            parts = [p.strip() for p in re.split(r",\s*(?=[A-Z\(])", stripped) if p.strip()]
            parts = [_strip_leading_percent(_strip_trailing_percent(p)) for p in parts]
            for x in parts:
                n = _normalize(x)
                if n and len(n) > 2:
                    ing_can = _canonicalize_ingredient(n)
                    if ing_can and ing_can not in seen and not _should_drop_ingredient_token(ing_can, strict=strict):
                        seen.add(ing_can)
                        uniq.append(ing_can)
    return uniq


def _confidence_weight(confidence: str) -> float:
    return CONFIDENCE_WEIGHT.get((confidence or "low").strip().lower(), 0.3)


def _saturate(x: float, cap: float) -> float:
    """Smooth saturation: growth slows as x approaches cap (reduces ties)."""
    if cap <= 0 or x <= 0:
        return 0.0
    return cap * math.log1p(x) / math.log1p(cap)


def _infer_tier(ingredient_name: str) -> str:
    """Infer active vs base from ingredient name for tier multiplier. MVP: keyword-based."""
    ing = (ingredient_name or "").lower()
    active_kw = (
        "retin", "retinal", "retinol", "peptide", "adenosine", "bakuchiol",
        "glycolic", "lactic", "salicylic", "ascorb", "niacinamide",
    )
    base_kw = ("glycerin", "glycerol", " oil", " oils", " butter", " butters", " fatty alcohol", "cetyl alcohol", "stearyl alcohol", "oleyl alcohol")
    for kw in active_kw:
        if kw in ing:
            return "active"
    for kw in base_kw:
        if kw in ing:
            return "base"
    return "other"


def _ingredient_family(ingredient_name: str) -> str:
    """Family for key-ingredient diversity and dry/wrinkle filter. Order matters. sebum_control before antioxidant."""
    ing = (ingredient_name or "").lower()
    # Do not infer family for description tokens so fallback does not become driver
    if _should_drop_ingredient_token(ingredient_name or ""):
        return "other"
    if any(x in ing for x in ("retin", "retinal", "retinol", "retinyl", "hydroxypinacolone retinoate")):
        return "retinoid"
    if "peptide" in ing or "hexapeptide" in ing or "pentapeptide" in ing or "tripeptide" in ing or "oligopeptide" in ing or "polypeptide" in ing:
        return "peptide"
    if any(x in ing for x in ("glycolic", "lactic", "salicylic", "aha", "bha", "phytic acid")):
        return "aha_bha"
    # sebum_control before antioxidant so niacinamide is oily-only display
    if any(x in ing for x in (
        "zinc pca", "zinc", "niacinamide", "sulfur", "tea tree",
        "kaolin", "bentonite", "charcoal", "silica",
    )):
        return "sebum_control"
    if any(x in ing for x in ("ascorb", "tocopher", "vitamin e", "vitamin c")):
        return "antioxidant"
    if any(x in ing for x in ("hyaluron", "glycerin", "glycerol", "panthenol", "urea", "sodium pca")):
        return "humectant"
    if any(x in ing for x in ("ceramide", "cholesterol", "fatty acid", "phytosphingosine")):
        return "barrier"
    if any(x in ing for x in ("squalane", "squalene", "seed oil", "fruit oil", " butter", "butter", "shea", "oil", "olea ", "jojoba", "argan", "avocado oil")):
        return "emollient"
    return "other"


def fallback_entry_from_family(ing: str) -> dict | None:
    """When ingredient not in skin_map, infer entry from family. Same schema as skin_map entry + source."""
    if not ing or not isinstance(ing, str):
        return None
    ing_lower = (ing or "").strip().lower()
    # Avoid: fragrance/irritant keywords -> avoid fallback
    if any(kw in ing_lower for kw in AVOID_FALLBACK_KEYWORDS):
        return {
            "skin_types": ["sensitive"],
            "effect": "avoid",
            "confidence": "medium",
            "tier": "other",
            "source": "fallback_family",
        }
    family = _ingredient_family(ing)
    if family == "retinoid":
        return {"skin_types": ["wrinkle"], "effect": "good", "confidence": "medium", "tier": "active", "source": "fallback_family"}
    if family == "peptide":
        return {"skin_types": ["wrinkle"], "effect": "good", "confidence": "medium", "tier": "active", "source": "fallback_family"}
    if family == "aha_bha":
        return {"skin_types": ["oily", "pigmentation"], "effect": "good", "confidence": "medium", "tier": "active", "source": "fallback_family"}
    if family == "antioxidant":
        return {"skin_types": ["pigmentation", "wrinkle"], "effect": "good", "confidence": "low", "tier": "active", "source": "fallback_family"}
    if family == "sebum_control":
        return {"skin_types": ["oily"], "effect": "good", "confidence": "medium", "tier": "active", "source": "fallback_family"}
    if family == "humectant":
        return {"skin_types": ["dry", "sensitive"], "effect": "good", "confidence": "medium", "tier": "base", "source": "fallback_family"}
    if family == "barrier":
        return {"skin_types": ["dry", "sensitive"], "effect": "good", "confidence": "medium", "tier": "base", "source": "fallback_family"}
    if family == "emollient":
        return {"skin_types": ["dry"], "effect": "good", "confidence": "low", "tier": "base", "source": "fallback_family"}
    # other -> no fallback
    return None


def score_product_mvp(
    ingredient_list: list,
    user_profile: dict,
    ingredient_skin_map: dict,
    paula_rating_map: dict,
    rating: float = 0,
    product_name: str = None,
) -> float:
    """
    Product score with:
    - Good -> bucket per type (tier mult). Avoid/poor -> penalty.
    - Normalization by ingredient count (sqrt(n) or n for kits) so long lists don't dominate.
    - Active saturation (wrinkle+pigmentation) via tanh for diminishing returns.
    - Sensitive/dry penalty for AHA, L-AA.
    - Marketing/complex tokens contribute 0.
    """
    bucket = defaultdict(float)
    sens = user_profile.get("sensitive", 0)
    dry_w = user_profile.get("dry", 0)
    n_scored = 0
    for ing in ingredient_list:
        if _is_marketing_no_score_ingredient(ing):
            continue
        n_scored += 1
        entry = ingredient_skin_map.get(ing) or fallback_entry_from_family(ing)
        if not entry:
            continue
        types = entry.get("skin_types") or []
        effect = (entry.get("effect") or "neutral").strip().lower()
        conf = (entry.get("confidence") or "low").strip().lower()
        w = _confidence_weight(conf)
        if entry.get("source") == "fallback_family":
            w *= FALLBACK_WEIGHT_MULT
        tier = entry.get("tier") or _infer_tier(ing)
        mult = TIER_MULT.get(tier, 1.0)
        if effect == "good":
            for t in types:
                mult_type = 0.5 if (t == "wrinkle" and "pigmentation" in types) else 1.0
                if t == "oily" and _ingredient_family(ing) in OILY_SUPPRESS_FAMILIES:
                    mult_type *= OILY_SUPPRESS_MULT
                bucket[t] += user_profile.get(t, 0) * TYPE_MULT.get(t, 1.0) * w * mult * mult_type
        elif effect == "avoid":
            bucket["avoid"] += (AVOID_PENALTY * (1.0 + 2.0 * sens)) * w
        if paula_rating_map.get(_paula_canonicalize(ing)) == "poor":
            bucket["poor"] += POOR_RATING_PENALTY

        # Sensitive/dry penalty for actives
        ing_low = (ing or "").lower()
        is_aha = any(x in ing_low for x in ("glycolic", "lactic", "salicylic", "aha", "bha", "phytic acid"))
        is_laa = "ascorb" in ing_low or "l-ascorbic" in ing_low
        if is_aha and (sens >= 0.1 or dry_w >= 0.8):
            bucket["penalty"] += SENSITIVE_AHA_PENALTY * w
        if is_laa and sens >= 0.1:
            bucket["penalty"] += SENSITIVE_LAA_PENALTY * w

    # INCI order-based strength proxy (small nudges)
    _apply_inci_strength_bonus(bucket, ingredient_list, user_profile)

    bucket["dry"] = _saturate(bucket["dry"], DRY_CAP)
    # Active saturation: wrinkle + pigmentation through tanh (diminishing returns)
    raw_wrinkle = bucket.get("wrinkle", 0)
    raw_pigmentation = bucket.get("pigmentation", 0)
    active_sum = raw_wrinkle + raw_pigmentation
    saturated_active = ACTIVE_SATURATION_A_MAX * math.tanh(active_sum / ACTIVE_SATURATION_TAU)
    total_good = (
        bucket["dry"] + bucket.get("normal", 0) + bucket.get("oily", 0) + bucket.get("sensitive", 0)
        + saturated_active
    )
    total = total_good - bucket.get("avoid", 0) - bucket.get("poor", 0) - bucket.get("penalty", 0)
    total += rating * RATING_WEIGHT

    # Normalization: only when n_ing is large (keep previous behavior for typical 10–35 ing products)
    n_ing = max(n_scored, 1)
    is_kit = False
    if product_name:
        pn_low = product_name.lower()
        is_kit = any(kw in pn_low for kw in KIT_NAME_KEYWORDS)
    if n_ing >= KIT_INGREDIENT_THRESHOLD:
        is_kit = True
    if n_ing <= NORM_APPLY_ABOVE and not is_kit:
        norm_factor = 1.0
    elif is_kit:
        norm_factor = math.sqrt(n_ing)  # kit: sqrt (was n_ing; softened so kits still appear)
    else:
        norm_factor = math.sqrt(n_ing)
    total = total / norm_factor
    return total


def get_key_ingredients(
    ingredient_list: list,
    user_profile: dict,
    ingredient_skin_map: dict,
    n: int = 3,
    target_types: list = None,
    diversify: bool = True,
    allow_families: list = None,
) -> list:
    """Top n ingredients (effect=good). target_types= filter by type; allow_families= restrict to families (e.g. dry: humectant,emollient,barrier; wrinkle: retinoid,peptide,aha_bha,antioxidant). diversify: at most 1 per family."""
    allow_families = set(allow_families or [])
    uniq_ings = []
    seen = set()
    for ing in ingredient_list:
        if ing and ing not in seen and not _is_marketing_no_score_ingredient(ing):
            seen.add(ing)
            uniq_ings.append(ing)
    contrib = []
    for ing in uniq_ings:
        if allow_families and _ingredient_family(ing) not in allow_families:
            continue
        entry = ingredient_skin_map.get(ing) or fallback_entry_from_family(ing)
        if not entry or (entry.get("effect") or "neutral").strip().lower() != "good":
            continue
        types = entry.get("skin_types") or []
        w = _confidence_weight(entry.get("confidence"))
        if entry.get("source") == "fallback_family":
            w *= FALLBACK_WEIGHT_MULT
        tier = entry.get("tier") or _infer_tier(ing)
        mult = TIER_MULT.get(tier, 1.0)
        score = 0.0
        for t in types:
            if target_types and t not in target_types:
                continue
            score += user_profile.get(t, 0) * TYPE_MULT.get(t, 1.0)
        score *= w * mult
        if score > 0:
            contrib.append((ing, score))
    contrib.sort(key=lambda x: -x[1])
    if not diversify:
        return [x[0] for x in contrib[:n]]
    # At most 1 per family so we don't show 3 peptides
    result = []
    families_used = set()
    for ing, sc in contrib:
        if len(result) >= n:
            break
        fam = _ingredient_family(ing)
        if fam not in families_used:
            families_used.add(fam)
            result.append(ing)
    for ing, sc in contrib:
        if len(result) >= n:
            break
        if ing not in result:
            result.append(ing)
    return result[:n]


def count_active_wrinkle_hits(ingredient_list: list, ingredient_skin_map: dict) -> int:
    """Count ingredients that are good, have wrinkle in types, and are tier=active (tie-breaker)."""
    seen = set()
    count = 0
    for ing in ingredient_list:
        if not ing or ing in seen:
            continue
        seen.add(ing)
        entry = ingredient_skin_map.get(ing) or fallback_entry_from_family(ing)
        if not entry or (entry.get("effect") or "neutral").strip().lower() != "good":
            continue
        types = entry.get("skin_types") or []
        if "wrinkle" not in types:
            continue
        tier = entry.get("tier") or _infer_tier(ing)
        if tier == "active":
            count += 1
    return count


def load_products_with_ingredients(max_products: int = None, use_sephora: bool = True):
    """
    Load products from final_data.csv.
    Returns list of {id, name, brand, ingredients, rating, raw_ingredients, source, product_url}.
    """
    if not FINAL_DATA_CSV.exists():
        return []
    products = []
    with open(FINAL_DATA_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if max_products is not None and i >= max_products:
                break
            source = row.get("source", "")
            if not use_sephora and source == "sephora":
                continue
            raw_ing = row.get("ingredients_parsed", "") or row.get("ingredients_raw", "") or ""
            raw_ing = " ".join(raw_ing.split())
            cls = _raw_ingredients_classification(raw_ing)
            if not cls.get("use_parser"):
                ingredients = []
                no_reason = cls.get("reason", "unknown")
                exclude_rec = True
            else:
                ingredients = _parse_ingredients(raw_ing)
                no_reason = None
                exclude_rec = False
                if not ingredients and _looks_like_marketing_only(raw_ing):
                    no_reason = "no_inci_provided"
                    exclude_rec = True
            try:
                rating = float(row.get("rating", 0) or 0)
            except Exception:
                rating = 0
            prod_name = (row.get("name") or "").strip()
            p = {
                "id": row.get("id") or str(i + 1),
                "name": prod_name,
                "brand": (row.get("brand") or "").strip(),
                "ingredients": ingredients,
                "ingredients_parsed": row.get("ingredients_parsed"),
                "rating": rating,
                "image_url": row.get("image_url"),
                "beneficial_ingredients": row.get("beneficial_ingredients"),
                "caution_ingredients": row.get("caution_ingredients"),
                "raw_ingredients": raw_ing[:200],
                "source": source,
                "product_url": (row.get("product_url") or "").strip(),
                "category": row.get("category") or categorize(prod_name, "", ""),
            }

            if no_reason:
                p["no_ingredients_reason"] = no_reason
            if exclude_rec:
                p["exclude_recommendation"] = True
            products.append(p)
    # Drop products that are disclaimer-only, dynamic formula, or non-cosmetic (no real ingredient data)
    _DROP_EMPTY_REASONS = ("no_ingredients_disclaimer", "dynamic_formula", "non_cosmetic_material")
    products = [
        p for p in products
        if (p.get("ingredients") or []) or p.get("no_ingredients_reason") not in _DROP_EMPTY_REASONS
    ]
    return products


def get_top_products(
    user_profile: dict,
    n: int = 10,
    max_products: int = None,
) -> list:
    """
    Returns list of dicts:
    - product: {id, name, brand, ingredients, rating}
    - score: float
    - key_ingredients: list of 3 ingredient names (why recommended)
    max_products=None (default) loads all cosmetics + all Sephora; set a number to limit for testing.
    """
    skin_map = load_ingredient_skin_map()
    paula_rating = load_paula_rating_map()
    products = load_products_with_ingredients(max_products=max_products)
    products = [p for p in products if not p.get("exclude_recommendation")]
    review_stats = load_review_stats()
    scored = []
    for p in products:
        # Match review stats: try "Brand + Name" then "Name" only (review_data item_reviewed is often product name only)
        review_key = _normalize(f"{p.get('brand','')} {p.get('name','')}")
        review_key_name_only = _normalize(p.get("name") or "")
        review_score = 0.0
        for key in (review_key, review_key_name_only):
            if key and key in review_stats:
                try:
                    review_score = float(review_stats[key].get("review_score", 0) or 0)
                except Exception:
                    review_score = 0.0
                break
        # Fallback: substring match (product name in review key or vice versa) when name is long enough; use average of all matches
        if review_score == 0.0 and review_key_name_only and len(review_key_name_only) >= 12:
            sub_scores = []
            for rk, data in review_stats.items():
                if not rk:
                    continue
                if review_key_name_only in rk or rk in review_key_name_only:
                    try:
                        s = float(data.get("review_score", 0) or 0)
                        if s > 0:
                            sub_scores.append(s)
                    except Exception:
                        pass
            if sub_scores:
                review_score = sum(sub_scores) / len(sub_scores)

        score = score_product_mvp(
            p["ingredients"],
            user_profile,
            skin_map,
            paula_rating,
            rating=p.get("rating", 0),
            product_name=(p.get("name") or "") + " " + (p.get("brand") or ""),
        )
        active_wrinkle_hits = count_active_wrinkle_hits(p["ingredients"], skin_map)
        primary = top_types(user_profile, k=6, min_w=0.1)
        key_by_type = {}
        used = set()
        for t in primary:
            keys_t = get_key_ingredients(
                p["ingredients"], user_profile, skin_map, n=3,
                target_types=[t], diversify=True,
                allow_families=TYPE_FAMILY_ALLOW.get(t),
            )
            keys_t = [k for k in keys_t if k not in used]
            used.update(keys_t)
            if not keys_t:
                keys_t = get_key_ingredients(
                    p["ingredients"], user_profile, skin_map, n=3,
                    target_types=[t], diversify=True, allow_families=None,
                )
                keys_t = [k for k in keys_t if k not in used]
                # Keep only allowed families for this type (e.g. oily: aha_bha, sebum_control only)
                allowed_fam = set(TYPE_FAMILY_ALLOW.get(t) or [])
                if allowed_fam:
                    keys_t = [k for k in keys_t if _ingredient_family(k) in allowed_fam]
                used.update(keys_t)
            key_by_type[t] = keys_t
        key_ingredients_flat = []
        for t in primary:
            key_ingredients_flat.extend(key_by_type.get(t, []))
        if not key_ingredients_flat:
            key_ingredients_flat = get_key_ingredients(
                p["ingredients"], user_profile, skin_map, n=3,
                target_types=None, diversify=True,
            )
        # Last-resort for oily/normal when skin_map has few good entries: show any ingredients in map
        if not key_ingredients_flat:
            seen_ing = set()
            for ing in p["ingredients"]:
                if ing and ing not in seen_ing and ing in skin_map and len(key_ingredients_flat) < 3:
                    seen_ing.add(ing)
                    key_ingredients_flat.append(ing)
        # Avoid ingredients in this product + why (skin_types from map = where it's bad)
        avoid_in_product = []
        for ing in p["ingredients"]:
            entry = skin_map.get(ing) or fallback_entry_from_family(ing)
            if entry and (entry.get("effect") or "").strip().lower() == "avoid":
                types = entry.get("skin_types") or []
                reason = ", ".join(types) if types else "irritant"
                avoid_in_product.append((ing, reason))
        # Why key ingredients are good (skin_types from map)
        key_ingredients_why = []
        for ing in key_ingredients_flat:
            entry = skin_map.get(ing) or fallback_entry_from_family(ing)
            types = (entry.get("skin_types") or []) if entry else []
            key_ingredients_why.append((ing, ", ".join(types) if types else "beneficial"))
        scored.append({
            "product": p,
            "base_score_raw": round(score, 4),
            "review_score_raw": round(review_score, 6),
            "key_ingredients": key_ingredients_flat,
            "key_ingredients_why": key_ingredients_why,
            "key_by_type": key_by_type,
            "active_wrinkle_hits": active_wrinkle_hits,
            "avoid_ingredients": avoid_in_product[:5],
        })

    # --- Top-100 selection, then min-max normalize to 0-100 ---
    TOP_POOL = len(scored)
    scored.sort(key=lambda x: (
        -(BASE_WEIGHT * x["base_score_raw"] + REVIEW_WEIGHT * x["review_score_raw"]),
        -x["active_wrinkle_hits"],
        -x["product"].get("rating", 0),
    ))
    scored = scored[:TOP_POOL]
    base_vals = [x["base_score_raw"] for x in scored]
    review_vals = [x["review_score_raw"] for x in scored]
    base_min, base_max = min(base_vals), max(base_vals)
    review_min, review_max = min(review_vals), max(review_vals)
    base_range = base_max - base_min if base_max != base_min else 1.0
    review_range = review_max - review_min if review_max != review_min else 1.0

    for item in scored:
        item["base_score"] = round((item["base_score_raw"] - base_min) * 100.0 / base_range, 2)
        item["review_score"] = round((item["review_score_raw"] - review_min) * 100.0 / review_range, 2)
        item["score"] = round(BASE_WEIGHT * item["base_score"] + REVIEW_WEIGHT * item["review_score"], 2)

    scored.sort(key=lambda x: (-x["score"], -x["active_wrinkle_hits"], -x["product"].get("rating", 0)))
    return scored[:n]


def user_input_to_profile(
    hydration_level: str = "normal",
    oil_level: str = "normal",
    sensitivity: str = "normal",
    age: int = None,
    concerns: list = None,
) -> dict:
    """Map user inputs to 6-type weights (0~1). Default all 0; only set when user specifies."""
    profile = {
        "dry": 0.0, "normal": 0.0, "oily": 0.0,
        "pigmentation": 0.0, "sensitive": 0.0, "wrinkle": 0.0,
    }
    if hydration_level == "low" or (concerns and "dryness" in concerns):
        profile["dry"] = 0.9
    if oil_level == "high":
        profile["oily"] = 0.9
    if sensitivity == "high":
        profile["sensitive"] = 0.9
    if concerns and "pigmentation" in concerns:
        profile["pigmentation"] = 0.9
    if (age is not None and age >= 35) or (concerns and "wrinkles" in concerns):
        profile["wrinkle"] = 0.9
    if all(profile[t] == 0.0 for t in profile):
        profile["normal"] = 0.5
    return profile


def _print_top(profile_label: str, profile: dict, top: list, n_show: int = 5):
    print(f"\nProfile ({profile_label}): {profile}")
    print(f"Top {n_show} products (scored out of 100):")
    for i, item in enumerate(top[:n_show], 1):
        p = item["product"]
        cat = p.get("category", "Other")
        line = f"  {i}. [{p['brand']}] {p['name'][:50]}  ({cat})"
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("ascii", errors="replace").decode("ascii"))
        print(f"      Total: {item['score']:.1f}/100  |  Base: {item['base_score']:.1f}  |  Review: {item['review_score']:.1f}")
        key_by_type = item.get("key_by_type") or {}
        for t, ings in key_by_type.items():
            if ings:
                print(f"      {t.capitalize()} drivers: {', '.join(ings)}")
        if not key_by_type or not any(key_by_type.values()):
            print(f"      Key ingredients: {item['key_ingredients']}")
        avoid = item.get("avoid_ingredients") or []
        if avoid:
            parts = [f"{ing} ({why})" for ing, why in avoid]
            print(f"      Avoid / Watch: {', '.join(parts)}")
        else:
            print(f"      Avoid / Watch: Avoid ingredients not found")

#Emily Added 
if __name__ == "__main__":

    profile = user_input_to_profile()

    # get ALL products
    results = get_top_products(profile, n=3000)

    output_path = DATA_DIR / "recommendations.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        writer.writerow([
            "brand",
            "name",
            "score",
            "base_score",
            "review_score",
            "key_ingredients",
            "image_url",
            "beneficial_ingredients",
            "caution_ingredients",
            "ingredients_parsed",
            "category"
        ])

        for item in results:

            p = item["product"]

            writer.writerow([
                p.get("brand"),
                p.get("name"),
                item["score"],
                item["base_score"],
                item["review_score"],
                ", ".join(item["key_ingredients"]),
                p.get("image_url"),
                p.get("beneficial_ingredients"),
                p.get("caution_ingredients"),
                ", ".join(p.get("ingredients", [])),
                p.get("category")
            ])

    print("Recommendations saved to:", output_path)