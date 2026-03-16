"""
Ingredient name normalization (same ingredient, different spellings -> single canonical form).
- Normalization + synonym table to reduce manufacturer/region/INCI/parentheses/abbrev/spacing/typo differences.
"""
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = ROOT / "cache"
INGREDIENT_ALIAS_PATH = CACHE_DIR / "ingredient_aliases.json"  # variant (norm) -> canonical (norm)


def normalize_ingredient(name: str) -> str:
    """Basic normalize: lower, trim, single space."""
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def paula_canonicalize(name: str) -> str:
    """
    Paula ingredient canonical form (STEP 1 reference universe):
    lower(), remove parentheses and content, remove periods, normalize space.
    """
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_strict(name: str, drop_parentheses: bool = True) -> str:
    """
    Strict normalization (unification step 1).
    - Trim leading/trailing whitespace and punctuation (., * ** etc.)
    - Lowercase, collapse spaces/tabs to single space
    - Normalize around slash: " / " -> " "
    - If drop_parentheses=True, remove parentheses and content: "Glycerin (Glycerol)" -> "glycerin"
    - Remove space between number+letter: "CI 77891" -> "ci 77891" (lowercase only)
    """
    if not name or not isinstance(name, str):
        return ""
    s = name.strip().lower()
    # Remove trailing punctuation/asterisks
    s = re.sub(r"[\s.*]+$", "", s)
    s = re.sub(r"^[\s.*]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Space around slash
    s = re.sub(r"\s*/\s*", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if drop_parentheses:
        s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
    return s


# Common abbreviations -> full name (lowercase). Applying before match helps unification.
COMMON_ABBREVIATIONS = {
    "ha": "hyaluronic acid",
    "bha": "salicylic acid",
    "aha": "alpha hydroxy acid",
    "bg": "butylene glycol",
    "pg": "propylene glycol",
    "edta": "edta",  # Keep as-is; disodium edta etc. are separate
    "uv": "uv",
    "spf": "spf",
    "ci ": "ci ",   # Keep color index numbers
}


def normalize_with_abbreviations(name: str, abbr_map: dict = None) -> str:
    """After normalize, if whole string is abbreviation replace with full name (whole-string only)."""
    s = normalize_strict(name, drop_parentheses=True)
    if not s:
        return s
    abbr = abbr_map or COMMON_ABBREVIATIONS
    # If whole string is abbreviation, replace
    if s in abbr:
        return abbr[s]
    # Per-word expansion (e.g. "sodium ha" -> "sodium hyaluronic acid") is optional; here whole only.
    return s


def load_ingredient_aliases() -> dict:
    """variant (normalized spelling) -> canonical (normalized unified name)."""
    if not INGREDIENT_ALIAS_PATH.exists():
        return {}
    try:
        with open(INGREDIENT_ALIAS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_ingredient_aliases(alias_map: dict):
    with open(INGREDIENT_ALIAS_PATH, "w", encoding="utf-8") as f:
        json.dump(alias_map, f, ensure_ascii=False, indent=2)


def canonicalize_ingredient(name: str, alias_map: dict = None) -> str:
    """
    Convert ingredient name to unified canonical form.
    1) normalize_strict + optional abbreviations
    2) If in alias_map return that canonical
    3) Else return normalized string (used as-is for matching)
    """
    if not name:
        return ""
    alias_map = alias_map if alias_map is not None else load_ingredient_aliases()
    norm = normalize_with_abbreviations(name)
    if not norm:
        return ""
    return alias_map.get(norm, norm)


def build_initial_aliases_from_paula(paula_normalized_set: set) -> dict:
    """
    Use Paula list as canonical; map each name to itself.
    Later add INCI Decoder/PubChem synonyms as variant -> paula_canonical.
    """
    alias = {}
    for p in paula_normalized_set:
        alias[p] = p
    return alias


def add_aliases_from_synonyms(alias_map: dict, synonym_pairs: list):
    """
    synonym_pairs: [(variant_norm, canonical_norm), ...]
    Skip if variant is already canonical; else add variant -> canonical.
    """
    for var, can in synonym_pairs:
        if not var or not can:
            continue
        if var == can:
            continue
        alias_map[var] = can
    return alias_map


def merge_aliases_from_matching_results(
    paula_via_incidecoder: dict,
    paula_via_pubchem: dict,
    save: bool = True,
) -> dict:
    """
    Merge this run's matching results (INCI Decoder / PubChem -> Paula) into alias table.
    Add variant (original ingredient norm) -> canonical (Paula-side norm).
    """
    alias_map = load_ingredient_aliases()
    for variant_norm, paula_canonical in paula_via_incidecoder.items():
        if variant_norm and paula_canonical and variant_norm != paula_canonical:
            alias_map[variant_norm] = paula_canonical
    for variant_norm, paula_canonical in paula_via_pubchem.items():
        if variant_norm and paula_canonical and variant_norm != paula_canonical:
            alias_map[variant_norm] = paula_canonical
    if save:
        save_ingredient_aliases(alias_map)
    return alias_map


# --- Usage (from other modules) ---
# from ingredient_canonical import canonicalize_ingredient, normalize_strict, load_ingredient_aliases
# canonical = canonicalize_ingredient("  Glycerin (Glycerol)  ")
# # Without alias: returns normalize_strict result "glycerin"
# # With alias "glycerin" -> "glycerin", "glycerol" -> "glycerin": both become "glycerin"
