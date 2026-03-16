"""
Sanity check: run recommendation for 10 different profiles and verify
- All types work (dry, normal, oily, pigmentation, sensitive, wrinkle)
- get_top_products returns results
- key_by_type keys match top_types(profile)
- No crashes, reasonable scores
"""
import sys
from pathlib import Path

# run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from recommend_mvp import (
    TYPE_FAMILY_ALLOW,
    _ingredient_family,
    get_top_products,
    load_ingredient_skin_map,
    score_product_mvp,
    top_types,
    user_input_to_profile,
)

# 10 profiles covering single-type, combos, and edge cases
TEST_PROFILES = [
    ("dry + wrinkle", user_input_to_profile(hydration_level="low", concerns=["wrinkles"])),
    ("oily only", {"dry": 0, "normal": 0, "oily": 0.9, "pigmentation": 0, "sensitive": 0, "wrinkle": 0}),
    ("sensitive only", {"dry": 0, "normal": 0, "oily": 0, "pigmentation": 0, "sensitive": 0.9, "wrinkle": 0}),
    ("pigmentation only", {"dry": 0, "normal": 0, "oily": 0, "pigmentation": 0.9, "sensitive": 0, "wrinkle": 0}),
    ("normal (default)", user_input_to_profile()),  # all 0 -> normal=0.5
    ("oily + sensitive", {"dry": 0, "normal": 0, "oily": 0.9, "pigmentation": 0, "sensitive": 0.9, "wrinkle": 0}),
    ("dry only", {"dry": 0.9, "normal": 0, "oily": 0, "pigmentation": 0, "sensitive": 0, "wrinkle": 0}),
    ("wrinkle only", {"dry": 0, "normal": 0, "oily": 0, "pigmentation": 0, "sensitive": 0, "wrinkle": 0.9}),
    ("pigmentation + wrinkle", {"dry": 0, "normal": 0, "oily": 0, "pigmentation": 0.9, "sensitive": 0, "wrinkle": 0.9}),
    ("dry + sensitive", {"dry": 0.9, "normal": 0, "oily": 0, "pigmentation": 0, "sensitive": 0.9, "wrinkle": 0}),
]

N_TOP = 5
MAX_PRODUCTS = 1500


def test_fallback_score_contributes():
    """Unknown (map-missing) ingredients with family-like names get fallback and score > 0."""
    skin_map = load_ingredient_skin_map()
    paula_rating = {}
    # Names that won't be in skin_map (synthetic) but match family keywords -> fallback
    fake_list = ["glycerin xyz test", "salicylic acid test", "retinol test variant"]
    profile = {"dry": 0.9, "normal": 0, "oily": 0, "pigmentation": 0, "sensitive": 0, "wrinkle": 0.9}
    score = score_product_mvp(fake_list, profile, skin_map, paula_rating, rating=0)
    # At least one of these should contribute via fallback (humectant, aha_bha, retinoid)
    if score <= 0:
        return False, "Fallback test: score should be > 0 for fake list with family keywords"
    return True, "Fallback contributes to score for map-missing ingredients"


def test_oily_drivers_no_retinoid_emollient_peptide():
    """Oily top 15: drivers should not be retinoid/emollient/peptide (WARN if present)."""
    profile = {"dry": 0, "normal": 0, "oily": 0.9, "pigmentation": 0, "sensitive": 0, "wrinkle": 0}
    top = get_top_products(profile, n=15, max_products=MAX_PRODUCTS)
    disallowed = {"retinoid", "emollient", "peptide"}
    allowed = set(TYPE_FAMILY_ALLOW.get("oily") or [])
    weird = []
    for item in top:
        for ing in (item.get("key_by_type") or {}).get("oily") or []:
            fam = _ingredient_family(ing)
            if fam in disallowed or (allowed and fam not in allowed):
                weird.append((ing, fam))
    if weird:
        sample = ", ".join([f"{ing}({fam})" for ing, fam in weird[:3]])
        return True, f"OK but [WARN] oily drivers outside allow: {sample}"
    return True, "Oily drivers within allow list"


def run_one(name: str, profile: dict) -> tuple[bool, str]:
    """Run get_top_products for one profile. Return (ok, message)."""
    try:
        primary = top_types(profile, k=2, min_w=0.1)
        top = get_top_products(profile, n=N_TOP, max_products=MAX_PRODUCTS)
    except Exception as e:
        return False, f"Exception: {e}"

    if not top:
        return False, "No products returned"

    # key_by_type keys should exist for each primary type (values may be empty if no matching ingredients)
    for i, item in enumerate(top):
        key_by_type = item.get("key_by_type") or {}
        for t in primary:
            if t not in key_by_type:
                return False, f"Missing key_by_type['{t}'] for product {i+1}"

    scores = [item["score"] for item in top]
    if not all(isinstance(s, (int, float)) for s in scores):
        return False, "Non-numeric score"

    any_keys = any(
        (item.get("key_ingredients") or any((item.get("key_by_type") or {}).values()))
        for item in top
    )
    labels = [t.capitalize() for t in primary]
    msg = f"OK (top types: {labels}, scores[:3]={scores[:3]})"
    if not any_keys:
        msg += " [WARN: no key drivers in top 5 - data may have few ingredients for this type]"

    # WARN: oily drivers should only be aha_bha / sebum_control
    if "oily" in primary:
        allowed = set(TYPE_FAMILY_ALLOW.get("oily") or [])
        weird = []
        for item in top:
            drivers = (item.get("key_by_type") or {}).get("oily") or []
            for ing in drivers:
                fam = _ingredient_family(ing)
                if allowed and fam not in allowed:
                    weird.append((ing, fam))
        if weird:
            sample = ", ".join([f"{ing}({fam})" for ing, fam in weird[:3]])
            msg += f" [WARN: odd oily drivers: {sample}]"

    return True, msg


def main():
    # Fallback and oily-driver sanity tests
    ok, msg = test_fallback_score_contributes()
    print("  [PASS]" if ok else "  [FAIL]", "fallback_score:", msg)
    if not ok:
        sys.exit(1)
    ok2, msg2 = test_oily_drivers_no_retinoid_emollient_peptide()
    print("  [PASS]" if ok2 else "  [FAIL]", "oily_drivers_check:", msg2)
    print("Sanity check: 10 profiles, top", N_TOP, "products each (max_products=", MAX_PRODUCTS, ")\n")
    passed = 0
    failed = []
    for name, profile in TEST_PROFILES:
        ok, msg = run_one(name, profile)
        if ok:
            passed += 1
            print(f"  [PASS] {name}: {msg}")
        else:
            failed.append(name)
            print(f"  [FAIL] {name}: {msg}")
    print()
    print(f"Result: {passed}/10 passed.")
    if failed:
        print("Failed profiles:", failed)
        sys.exit(1)
    print("All profiles OK.")
    sys.exit(0)


if __name__ == "__main__":
    main()
