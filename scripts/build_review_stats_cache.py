"""
Build review stats cache from review_data.csv.
Output: review_stats.json

review_score = avg_norm_rating * log1p(count) * recentness
recentness = exp(-days_since_last / 180)
"""
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
REVIEW_CSV = DATA_DIR / "review_data.csv"
OUT_JSON = CACHE_DIR / "review_stats.json"


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().lower()
    s = " ".join(s.split())
    return s


def _parse_date(s: str):
    """Parse ISO date; fallback None."""
    if not s:
        return None
    s = str(s).strip()
    try:
        # Handles "YYYY-MM-DD" or ISO with time
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def main():
    if not REVIEW_CSV.exists():
        print(f"[ERROR] Missing: {REVIEW_CSV}")
        return

    rows = []
    with open(REVIEW_CSV, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            item = _normalize(r.get("item_reviewed", ""))
            if not item:
                continue
            try:
                rv = float(r.get("rating_value", 0) or 0)
                br = float(r.get("best_rating", 5) or 5)
                if br <= 0:
                    br = 5.0
            except Exception:
                continue
            dt = _parse_date(r.get("date_published", ""))
            rows.append((item, rv / br, dt))

    # Aggregate per product_name
    agg = {}
    for item, norm_rating, dt in rows:
        a = agg.setdefault(item, {"sum": 0.0, "cnt": 0, "last": None})
        a["sum"] += norm_rating
        a["cnt"] += 1
        if dt:
            if a["last"] is None or dt > a["last"]:
                a["last"] = dt

    now = datetime.now(timezone.utc)
    out = {}
    for item, a in agg.items():
        cnt = int(a["cnt"])
        if cnt <= 0:
            continue
        avg = float(a["sum"]) / cnt  # 0~1
        if a["last"] is None:
            recentness = 0.7  # unknown recency -> mild penalty
        else:
            days = max(0.0, (now - a["last"]).total_seconds() / 86400.0)
            recentness = math.exp(-days / 180.0)
        review_score = avg * math.log1p(cnt) * recentness
        out[item] = {
            "avg": round(avg, 6),
            "count": cnt,
            "recentness": round(recentness, 6),
            "review_score": round(review_score, 6),
        }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] Wrote {OUT_JSON} ({len(out)} products)")


if __name__ == "__main__":
    main()
