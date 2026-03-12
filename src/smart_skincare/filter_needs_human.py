"""
Auto-filter needs_human.csv so only items for human/rule-fill remain.

1) Drop "no human needed": forbidden keywords (complex|technology|division|visibly|helps|...)
2) Strip numbers/units from name for normalized form: %|kda|g|mg|24k|spf
3) Typo/synonym normalization (rule-based): hexanediol variants, coq10/ubiquinone, tocopherol etc.
   If normalized form is already in skin_map, skip (no human needed).
4) Keep only "plausible ingredients": Latin/plant/oil/extract-like names.
5) Output: needs_human_filtered.csv (for human/rule-fill, low confidence).
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"
CACHE_DIR = ROOT / "cache"
NEEDS_HUMAN_CSV = DATA_DIR / "needs_human.csv"
NEEDS_HUMAN_FILTERED_CSV = DATA_DIR / "needs_human_filtered.csv"

# Forbidden: if ingredient contains any of these → drop (no human needed)
FORBIDDEN_KEYWORDS = re.compile(
    r"complex|technology|system|division|visibly|helps?|boosts?|reduce[sd]?|improving|"
    r"for eyes|subject to change|please consult|amount per serving|timezone|sync |matrix |"
    r"age rvr|repr |rec cmp|rcvr |conc matrix|int rcv|eye crm|eye sr",
    re.I
)

# Strip from name for normalized form (numbers/units)
STRIP_PATTERN = re.compile(
    r"\s*\d+(?:\.\d+)?\s*%|\s*\d+\s*kda\b|\s*\d+\s*g\b|\s*\d+\s*mg\b|"
    r"\s*24k\b|\s*spf\s*\d*|\s*\d+\s*(?:and|&)\s*\d+\s*kda\)?|"
    r"^\d+\s*\)\s*|-?\s*\d+\s*$",
    re.I
)

def _normalize(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"^[\s*.\-]+\s*", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def strip_numbers_units(name: str) -> str:
    """Remove %|kda|g|mg|24k|spf etc. for normalized display."""
    s = name
    for _ in range(5):
        s2 = STRIP_PATTERN.sub(" ", s)
        s2 = re.sub(r"\s+", " ", s2).strip()
        if s2 == s:
            break
        s = s2
    return _normalize(s)


# Typo/synonym → canonical (for "already in map" check or auto-fill)
SYNONYM_RULES = [
    # hexanediol variants
    (r"1\s*,\s*2\s*hexanedi?ol", "1,2-hexanediol"),
    (r"1\s*,\s*2\s*hexanidiol", "1,2-hexanediol"),
    (r"1\s*,\s*2\s*hexandiol", "1,2-hexanediol"),
    (r"1\s*,\s*2\s*heanediol", "1,2-hexanediol"),
    (r"1\s*,\s*2\s*hexanedio\b", "1,2-hexanediol"),
    (r"1\s*,\s*10\s*decanediol", "1,10-decanediol"),
    # coq10 / ubiquinone
    (r"coq\s*10|coenzyme\s*q\s*10", "coenzyme q10"),
    (r"ubiquinone", "coenzyme q10"),
    # tocopherol
    (r"tocopher[eo]ls?", "tocopherol"),
    (r"acsorbyl", "ascorbyl"),
    (r"acetyle?\s*glucosamine", "acetyl glucosamine"),
    (r"ascorbyl\s*palmitate", "ascorbyl palmitate"),
    (r"activated\s*c\b", "ascorbic acid"),
    (r"acv\b", "apple cider vinegar"),
]
SYNONYM_COMPILED = [(re.compile(p, re.I), c) for p, c in SYNONYM_RULES]


def normalize_synonym(name: str) -> str:
    """Rule-based typo/synonym → canonical form."""
    n = _normalize(name)
    for pat, canonical in SYNONYM_COMPILED:
        if pat.search(n) or pat.sub("", n).replace(" ", "") == canonical.replace(" ", ""):
            return canonical
    return n


# Short known actives (keep for human/rule-fill even if short)
SHORT_ACTIVES = {"4msk", "txa", "pha", "ha", "bg", "pg", "edta", "bha", "aha", "acv", "retinol", "uv"}

# Plausible ingredient: Latin/plant/oil/extract patterns (keep for human/rule-fill)
PLAUSIBLE_PATTERNS = re.compile(
    r"oil\b|extract\b|flower\b|seed\b|root\b|leaf\b|fruit\b|berry\b|kernel\b|"
    r"bark\b|stem\b|juice\b|ferment\b|butter\b|wax\b|"
    r"officinalis|sinensis|alba| vulgaris| arvensis| sativa| indica|"
    r"americana| asiatica| europaea| japonica| montana|"
    r"[a-z]+\s+[a-z]+\s+(?:oil|extract|water|powder)\b",
    re.I
)


def is_plausible_ingredient(name: str) -> bool:
    n = _normalize(name)
    if len(n) < 2 or len(n) > 80:
        return False
    if n in SHORT_ACTIVES:
        return True
    if PLAUSIBLE_PATTERNS.search(n):
        return True
    # Chemical-like: has hyphen or comma
    if re.search(r"[-,]", n) and re.search(r"[a-z]{3,}", n):
        return True
    if len(n.split()) >= 2 and re.search(r"[a-z]{4,}", n):
        return True
    # Single word Latin/plant-like (4–25 letters)
    if re.match(r"^[a-z]{4,25}$", n) and not re.match(r"^\d", n):
        return True
    return False


def main():
    if not NEEDS_HUMAN_CSV.exists():
        print(f"Missing {NEEDS_HUMAN_CSV.name}; run fill_curation_rules.py first.")
        return

    # Load skin_map to skip already-known
    skin_map = {}
    skin_map_path = CACHE_DIR / "ingredient_skin_map.json"
    if skin_map_path.exists():
        import json
        with open(skin_map_path, encoding="utf-8") as f:
            skin_map = json.load(f)
    skin_map_keys_norm = {_normalize(k) for k in skin_map}

    rows = []
    with open(NEEDS_HUMAN_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ing = (row.get("ingredient") or "").strip()
            if ing:
                rows.append(ing)

    dropped = []
    auto_resolved = []
    plausible = []

    for ing in rows:
        n = _normalize(ing)
        # 1) Forbidden keywords → drop
        if FORBIDDEN_KEYWORDS.search(ing) or FORBIDDEN_KEYWORDS.search(n):
            dropped.append(ing)
            continue
        # 2) Strip numbers/units for normalized form
        name_clean = strip_numbers_units(ing)
        if not name_clean or len(name_clean) < 2:
            dropped.append(ing)
            continue
        # 3) Synonym normalize; if already in map → auto_resolved
        canon = normalize_synonym(name_clean)
        if _normalize(canon) in skin_map_keys_norm:
            auto_resolved.append((ing, canon))
            continue
        # 4) Only plausible (Latin/plant/oil/extract) → for human/rule-fill
        if not is_plausible_ingredient(name_clean):
            dropped.append(ing)
            continue
        plausible.append(ing)

    # Dedupe plausible by normalized form
    seen = set()
    plausible_uniq = []
    for ing in plausible:
        k = _normalize(ing)
        if k not in seen:
            seen.add(k)
            plausible_uniq.append(ing)

    # Write needs_human_filtered.csv (for human/rule-fill; suggest confidence=low)
    with open(NEEDS_HUMAN_FILTERED_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ingredient", "skin_type", "effect", "confidence"])
        w.writeheader()
        for ing in sorted(plausible_uniq):
            w.writerow({"ingredient": ing, "skin_type": "", "effect": "", "confidence": ""})
    print(f"needs_human_filtered.csv: {len(plausible_uniq)} rows (for human/rule-fill, plausible only)")


if __name__ == "__main__":
    main()
