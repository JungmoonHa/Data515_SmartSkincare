"""
Next step — Run recommendation from command line with your profile.
Usage:
  python run_recommendation.py
  python run_recommendation.py --dry --wrinkle
  python run_recommendation.py --hydration low --oil high --age 40 --top 5
"""
import argparse
from recommend_mvp import user_input_to_profile, get_top_products


def main():
    ap = argparse.ArgumentParser(description="Smart Skincare MVP: get top product recommendations")
    ap.add_argument("--hydration", choices=["low", "normal", "high"], default="normal", help="Hydration level")
    ap.add_argument("--oil", choices=["low", "normal", "high"], default="normal", help="Oil level")
    ap.add_argument("--sensitivity", choices=["low", "normal", "high"], default="normal", help="Sensitivity")
    ap.add_argument("--age", type=int, default=None, help="Age (e.g. 35+ boosts wrinkle weight)")
    ap.add_argument("--dry", action="store_true", help="Shortcut: dryness concern")
    ap.add_argument("--oily", action="store_true", help="Shortcut: oily concern")
    ap.add_argument("--wrinkle", action="store_true", help="Shortcut: wrinkles concern")
    ap.add_argument("--pigmentation", action="store_true", help="Shortcut: pigmentation concern")
    ap.add_argument("--top", type=int, default=10, help="Number of top products (default 10)")
    ap.add_argument("--max-products", type=int, default=None, metavar="N", help="Max products to score (default: all)")
    args = ap.parse_args()

    concerns = []
    if args.dry:
        concerns.append("dryness")
    if args.wrinkle:
        concerns.append("wrinkles")
    if args.pigmentation:
        concerns.append("pigmentation")

    profile = user_input_to_profile(
        hydration_level=args.hydration,
        oil_level=args.oil,
        sensitivity=args.sensitivity,
        age=args.age,
        concerns=concerns if concerns else None,
    )
    print("Profile (6-type weights):", profile)
    print()

    top = get_top_products(profile, n=args.top, max_products=args.max_products)
    print(f"Top {len(top)} products:")
    for i, item in enumerate(top, 1):
        p = item["product"]
        print(f"  {i}. [{p['brand']}] {p['name'][:55]} (score={item['score']})")
        print(f"      Key ingredients: {', '.join(item['key_ingredients'][:3])}")


if __name__ == "__main__":
    main()
