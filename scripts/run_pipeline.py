"""
Run curation + build pipeline in order (STEP 5), then optionally recommendation.

Order: filter_needs_human → apply_curation_rules_v2 → fill_needs_human_withSearch
       → fill_remaining_not_in_map → build_ingredient_skin_map
       → (optional) recommend_mvp

Usage: python run_pipeline.py
       python run_pipeline.py --recommend   # run recommend_mvp at the end
"""
import subprocess
import sys
import argparse
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

STEPS = [
    ("filter_needs_human.py", "Filter needs_human → needs_human_filtered"),
    ("apply_curation_rules_v2.py", "Rule pass A–D → needs_human_filtered_v2"),
    ("fill_needs_human_withSearch.py", "Rule-fill needs_human_filtered_v2 → withSearch_filled_v2"),
    ("fill_remaining_not_in_map.py", "Fill remaining not-in-map → withSearch_filled_remaining"),
    ("build_ingredient_skin_map.py", "Merge all → ingredient_skin_map.json"),
]


def run(script: str) -> bool:
    """Run a Python script in this directory. Return True if success."""
    code = subprocess.call([sys.executable, str(SCRIPTS_DIR / script)], cwd=str(SCRIPTS_DIR))
    return code == 0


def main():
    ap = argparse.ArgumentParser(description="Run curation + build pipeline (STEP 5).")
    ap.add_argument("--recommend", action="store_true", help="Run recommend_mvp.py at the end")
    args = ap.parse_args()

    for i, (script, desc) in enumerate(STEPS, 1):
        print("=" * 60)
        print(f"{i}. {script} — {desc}")
        print("=" * 60)
        if not run(script):
            print(f"Failed: {script}")
            sys.exit(1)
        print()

    if args.recommend:
        print("=" * 60)
        print("6. recommend_mvp.py")
        print("=" * 60)
        if not run("recommend_mvp.py"):
            print("Failed: recommend_mvp.py")
            sys.exit(1)
        print()

    print("Pipeline done.")


if __name__ == "__main__":
    main()
