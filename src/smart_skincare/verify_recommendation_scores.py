"""
Verify that all products in the recommendation pool get a proper score.
Reports: total pool, score distribution, how many have score > 0 vs == 0.
"""
from collections import defaultdict

from recommend_mvp import (
    load_products_with_ingredients,
    load_ingredient_skin_map,
    load_paula_rating_map,
    score_product_mvp,
)


def safe_print(s):
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", errors="replace").decode("ascii"))


def run_audit(profile: dict, profile_name: str):
    products = load_products_with_ingredients(max_products=None)
    products = [p for p in products if not p.get("exclude_recommendation")]

    skin_map = load_ingredient_skin_map()
    paula_rating = load_paula_rating_map()

    scores = []
    zero_score_products = []

    for p in products:
        score = score_product_mvp(
            p.get("ingredients") or [],
            profile,
            skin_map,
            paula_rating,
            rating=p.get("rating", 0),
        )
        scores.append(score)
        if score == 0:
            zero_score_products.append((p.get("brand", ""), p.get("name", "")[:50], len(p.get("ingredients") or [])))

    total = len(scores)
    positive = sum(1 for s in scores if s > 0)
    zero = total - positive
    if not scores:
        safe_print(f"[{profile_name}] No products in pool.")
        return
    mn = min(scores)
    mx = max(scores)
    mean = sum(scores) / len(scores)
    scores_sorted = sorted(scores, reverse=True)
    p50 = scores_sorted[len(scores_sorted) // 2] if scores_sorted else 0
    p90 = scores_sorted[int(len(scores_sorted) * 0.9)] if scores_sorted else 0

    safe_print(f"\n--- Profile: {profile_name} ---")
    safe_print(f"  Pool size: {total}")
    safe_print(f"  With score > 0: {positive}  |  With score == 0: {zero}")
    safe_print(f"  Score: min={mn:.4f}  max={mx:.4f}  mean={mean:.4f}  p50={p50:.4f}  p90={p90:.4f}")
    if zero_score_products:
        safe_print(f"  Sample products with score 0 (first 5):")
        for brand, name, n_ing in zero_score_products[:5]:
            safe_print(f"    - [{brand}] {name}  (ingredients: {n_ing})")


def main():
    print("Loading products and running score audit...")
    # Balanced profile
    profile_balanced = {
        "dry": 0.3, "normal": 0.2, "oily": 0.2,
        "pigmentation": 0.2, "sensitive": 0.1, "wrinkle": 0.3,
    }
    run_audit(profile_balanced, "balanced")

    profile_dry_wrinkle = {"dry": 0.8, "normal": 0, "oily": 0, "pigmentation": 0.2, "sensitive": 0.2, "wrinkle": 0.6}
    run_audit(profile_dry_wrinkle, "dry+wrinkle")

    profile_oily = {"dry": 0, "normal": 0, "oily": 0.9, "pigmentation": 0, "sensitive": 0, "wrinkle": 0}
    run_audit(profile_oily, "oily")

    print("\n--- Summary ---")
    print("All products in the pool receive a score (no product is skipped).")
    print("Products with score > 0 can appear in top-N recommendations; score=0 are ranked at the bottom.")
    print("Done.")


if __name__ == "__main__":
    main()
