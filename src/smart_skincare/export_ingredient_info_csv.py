"""
Export combined ingredient info to a single CSV.

Input:
- ingredient_skin_map.json
- ingredient_info_incidecoder.json

Output:
- ingredient_info_combined.csv
"""
import csv
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIN_MAP_PATH = ROOT / "ingredient_skin_map.json"
INCI_INFO_PATH = ROOT / "ingredient_info_incidecoder.json"
OUT_CSV_PATH = ROOT / "ingredient_info_combined.csv"


def _normalize_key(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _join_list(value) -> str:
    if not isinstance(value, list):
        return ""
    return "; ".join(str(v).strip() for v in value if str(v).strip())


def main():
    skin_map = _load_json(SKIN_MAP_PATH)
    inci_info = _load_json(INCI_INFO_PATH)

    all_keys = sorted(set(skin_map.keys()) | set(inci_info.keys()), key=str.lower)
    rows = []

    for raw_key in all_keys:
        key = _normalize_key(raw_key)
        s = skin_map.get(raw_key, {})
        i = inci_info.get(raw_key, {})

        skin_types = []
        effect = ""
        confidence = ""
        if isinstance(s, list):
            skin_types = s
            effect = "good"
            confidence = "medium"
        elif isinstance(s, dict):
            skin_types = s.get("skin_types") or []
            effect = (s.get("effect") or "").strip()
            confidence = (s.get("confidence") or "").strip()

        what_it_does = _join_list(i.get("what_it_does")) if isinstance(i, dict) else ""
        details = ""
        if isinstance(i, dict):
            details = html.unescape((i.get("details") or "").strip())

        rows.append(
            {
                "ingredient": key,
                "in_skin_map": 1 if raw_key in skin_map else 0,
                "in_incidecoder": 1 if raw_key in inci_info else 0,
                "skin_types": _join_list(skin_types),
                "effect": effect,
                "confidence": confidence,
                "inci_source": (i.get("source") or "").strip() if isinstance(i, dict) else "",
                "inci_slug": (i.get("slug") or "").strip() if isinstance(i, dict) else "",
                "inci_what_it_does": what_it_does,
                "inci_details": details,
            }
        )

    fieldnames = [
        "ingredient",
        "in_skin_map",
        "in_incidecoder",
        "skin_types",
        "effect",
        "confidence",
        "inci_source",
        "inci_slug",
        "inci_what_it_does",
        "inci_details",
    ]
    with open(OUT_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"[OK] Wrote: {OUT_CSV_PATH}")
    print(f"[OK] Rows: {len(rows)}")


if __name__ == "__main__":
    main()
