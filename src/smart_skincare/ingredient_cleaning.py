"""
Raw ingredient cleaning before matching (STEP 2).
- Remove parentheses and content
- Remove percentage suffixes e.g. (6.993%)
- Split compound ingredients by ", "
- Filter junk: long strings with "visit", split on "ingredients:"
"""
import re


def _remove_percent(s: str) -> str:
    """Remove trailing (6.993%) or (6%) style suffixes."""
    s = re.sub(r"\s*\(\s*\d+\.?\d*%?\s*\)\s*$", "", s)
    s = re.sub(r"\s*\(\s*\d+\.?\d*%?\s*\)", " ", s)
    return s.strip()


def _remove_parentheses(s: str) -> str:
    """Remove parentheses and their content."""
    return re.sub(r"\s*\([^)]*\)\s*", " ", s)


def _normalize_space(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _remove_periods(s: str) -> str:
    """Remove periods (e.g. for Paula canonical)."""
    return s.replace(".", "")


def clean_one_ingredient(raw: str) -> str:
    """
    Clean a single ingredient string:
    - lower, normalize space
    - remove parentheses and content
    - remove percentage parts like (6.993%)
    - remove periods
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = raw.strip().lower()
    s = _remove_parentheses(s)
    s = _remove_percent(s)
    s = _remove_periods(s)
    s = _normalize_space(s)
    return s


def is_junk(ingredient: str) -> bool:
    """
    Filter out junk: length >= 40 and contains "visit", or similar.
    """
    if not ingredient or len(ingredient) < 2:
        return True
    s = ingredient.lower()
    if len(s) >= 40 and "visit" in s:
        return True
    if "visit the boutique" in s:
        return True
    return False


def split_on_ingredients_label(text: str) -> list:
    """
    If text contains "ingredients:", return list of parts after it (split by ", ").
    Otherwise return [text].
    """
    if not text or "ingredients:" not in text.lower():
        return [text] if text else []
    idx = text.lower().index("ingredients:")
    after = text[idx + len("ingredients:"):].strip()
    if not after:
        return []
    return [p.strip() for p in re.split(r",\s+", after) if p.strip()]


def split_compound(raw: str) -> list:
    """
    Split compound ingredient string by ", " (comma space).
    e.g. "phenoxyethanol, 1,2-hexanediol" -> ["phenoxyethanol", "1,2-hexanediol"]
    """
    if not raw or not isinstance(raw, str):
        return []
    parts = re.split(r",\s+", raw)
    return [p.strip() for p in parts if p.strip()]


def clean_raw_ingredient(raw: str) -> list:
    """
    From one raw ingredient string (possibly compound), return list of cleaned
    single-ingredient strings. Junk is dropped.
    - Handles "ingredients:" by taking text after it
    - Splits compounds by ", "
    - Removes parens, %, periods, normalizes space
    - Drops junk (e.g. long + "visit")
    """
    if not raw or not isinstance(raw, str):
        return []
    # First: if "ingredients:" present, take part after it and split
    chunks = split_on_ingredients_label(raw)
    out = []
    for chunk in chunks:
        for part in split_compound(chunk):
            cleaned = clean_one_ingredient(part)
            if cleaned and not is_junk(cleaned) and len(cleaned) > 2:
                out.append(cleaned)
    return out
