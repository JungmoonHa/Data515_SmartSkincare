"""One-off: count how many recommendation-pool products still lack an image URL."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = ROOT / "cache"

def _normalize(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"^[\s*.\-]+\s*", "", s)
    return re.sub(r"\s+", " ", s).strip()

def main():
    from recommend_mvp import load_products_with_ingredients
    pool = [p for p in load_products_with_ingredients() if not p.get("exclude_recommendation")]
    cos_path = CACHE_DIR / "cosmetics_image_urls.json"
    sep_path = CACHE_DIR / "sephora_image_urls.json"
    cos_out = json.loads(cos_path.read_text(encoding="utf-8")) if cos_path.exists() else {}
    sep_out = json.loads(sep_path.read_text(encoding="utf-8")) if sep_path.exists() else {}
    cos_out_n = {_normalize(k): v for k, v in cos_out.items()}
    sep_out_n = {_normalize(k): v for k, v in sep_out.items()}
    have = 0
    for p in pool:
        brand = (p.get("brand") or "").strip()
        name = (p.get("name") or "").strip()
        nk = _normalize(brand + " " + name)
        pu = (p.get("product_url") or "").strip()
        src = p.get("source") or "cosmetics"
        if src == "cosmetics":
            if nk in cos_out_n:
                have += 1
        else:
            if (pu and _normalize(pu) in sep_out_n) or nk in sep_out_n:
                have += 1
    missing = len(pool) - have
    print("pool:", len(pool), "with_image:", have, "missing:", missing)

if __name__ == "__main__":
    main()
