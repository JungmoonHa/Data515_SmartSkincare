"""
Fetch product image URLs for recommendation-pool products that don't have one yet.
Uses only Serper API (search + image search fallback). No OpenAI, no DuckDuckGo/Bing.

- Loads pool via recommend_mvp.load_products_with_ingredients (exclude_recommendation excluded).
- Only processes products that are missing from cosmetics_image_urls.json / sephora_image_urls.json.
- Query = "brand name". Serper search -> first result pages -> og:image; if all fail -> Serper image search.

Requires: pip install requests beautifulsoup4
Env: SERPER_API_KEY (required)

Usage:
  SERPER_API_KEY=xxx python fetch_product_images_byHand.py
  SERPER_API_KEY=xxx python fetch_product_images_byHand.py --max 100   # cap at 100
"""
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "Datasets"
CACHE_DIR = ROOT / "cache"
COSMETICS_CSV = DATA_DIR / "cosmetics.csv"
SEPHORA_CSV = DATA_DIR / "Sephora_all_423.csv"
OUT_COSMETICS_JSON = CACHE_DIR / "cosmetics_image_urls.json"
OUT_SEPHORA_JSON = CACHE_DIR / "sephora_image_urls.json"
REQUEST_DELAY_SEC = 1.5
SERPER_SEARCH_URL = "https://google.serper.dev/search"
SERPER_IMAGES_URL = "https://google.serper.dev/images"


def _normalize(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    s = s.strip().lower()
    s = re.sub(r"^[\s*.\-]+\s*", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_pool_missing(serper_key: str) -> list:
    """Load recommendation pool, return list of (norm_key, brand, name, product_url, source) that lack image."""
    if not (serper_key or "").strip():
        raise SystemExit("SERPER_API_KEY is required. Set env or pass --serper-key.")
    try:
        from recommend_mvp import load_products_with_ingredients
    except ImportError:
        raise SystemExit("recommend_mvp not found. Run from project root.")
    all_ = load_products_with_ingredients()
    pool = [p for p in all_ if not p.get("exclude_recommendation")]
    cos_out = _load_json(OUT_COSMETICS_JSON)
    sep_out = _load_json(OUT_SEPHORA_JSON)
    cos_out = {_normalize(k): v for k, v in cos_out.items()}
    sep_out = {_normalize(k): v for k, v in sep_out.items()}
    missing = []
    for p in pool:
        brand = (p.get("brand") or "").strip()
        name = (p.get("name") or "").strip()
        nk = _normalize(brand + " " + name)
        if not nk:
            continue
        pu = (p.get("product_url") or "").strip()
        if pu and not pu.startswith("http"):
            pu = ""
        src = p.get("source") or "cosmetics"
        if src == "cosmetics":
            if nk in cos_out:
                continue
            missing.append((nk, brand, name, None, "cosmetics"))
        else:
            if (pu and _normalize(pu) in sep_out) or nk in sep_out:
                continue
            missing.append((nk, brand, name, pu or None, "sephora"))
    return missing


def _serper_search(query: str, api_key: str, num: int = 5) -> list[str]:
    """Return list of result URLs from Serper search."""
    try:
        import requests
    except ImportError:
        return []
    headers = {"X-API-KEY": api_key.strip(), "Content-Type": "application/json"}
    payload = {"q": query, "num": num}
    try:
        r = requests.post(SERPER_SEARCH_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        urls = []
        for obj in data.get("organic") or []:
            link = (obj.get("link") or "").strip()
            if link.startswith("http"):
                urls.append(link)
        return urls[:num]
    except Exception:
        return []


def _serper_image_search(query: str, api_key: str) -> str:
    """Return first image URL from Serper image search, or empty string."""
    try:
        import requests
    except ImportError:
        return ""
    headers = {"X-API-KEY": api_key.strip(), "Content-Type": "application/json"}
    payload = {"q": query, "num": 1}
    try:
        r = requests.post(SERPER_IMAGES_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        images = data.get("images") or []
        if images and isinstance(images[0], dict):
            return (images[0].get("imageUrl") or images[0].get("link") or "").strip()
        if images and isinstance(images[0], str):
            return images[0].strip()
        return ""
    except Exception:
        return ""


def _fetch_og_image(url: str) -> tuple[str, str]:
    """Fetch URL, return (og:image URL, error_message)."""
    try:
        import requests
    except ImportError:
        return "", "no requests/beautifulsoup4"
    try:
        r = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return "", str(e)[:80]
    m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1).strip(), ""
    return "", "no og:image"


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Fetch missing product image URLs (Serper only, pool only)")
    ap.add_argument("--max", type=int, default=0, help="Max products to process (0 = all missing). Default 0.")
    ap.add_argument("--delay", type=float, default=REQUEST_DELAY_SEC, help="Seconds between requests")
    ap.add_argument("--serper-key", type=str, default="", help="Serper API key (default: SERPER_API_KEY env)")
    ap.add_argument("--verbose", "-v", action="store_true", help="Print per-product progress")
    args = ap.parse_args()
    serper_key = (args.serper_key or os.environ.get("SERPER_API_KEY") or "").strip()
    if not serper_key:
        raise SystemExit("SERPER_API_KEY is required. Set env or --serper-key.")

    missing = _load_pool_missing(serper_key)
    if args.max > 0:
        missing = missing[: args.max]
    print(f"[INFO] Recommendation pool: {len(missing)} products missing image (Serper only)")

    cos_out = _load_json(OUT_COSMETICS_JSON)
    sep_out = _load_json(OUT_SEPHORA_JSON)
    cos_out = {_normalize(k): v for k, v in cos_out.items()}
    sep_out = {_normalize(k): v for k, v in sep_out.items()}

    def save():
        OUT_COSMETICS_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_COSMETICS_JSON.write_text(json.dumps(cos_out, ensure_ascii=False, indent=2), encoding="utf-8")
        OUT_SEPHORA_JSON.write_text(json.dumps(sep_out, ensure_ascii=False, indent=2), encoding="utf-8")

    done = 0
    try:
        for idx, (norm_key, brand, name, product_url, src) in enumerate(missing):
            query = f"{brand} {name}"
            if args.verbose:
                print(f"  [{idx+1}/{len(missing)}] {query[:60]}...")
            urls = _serper_search(query, serper_key, num=5)
            img = ""
            for u in urls:
                img, _ = _fetch_og_image(u)
                if img:
                    break
                time.sleep(0.3)
            if not img:
                img = _serper_image_search(query, serper_key)
                if img and args.verbose:
                    print("      -> image (from image search)")
            if img:
                if src == "cosmetics":
                    cos_out[norm_key] = img
                else:
                    if product_url:
                        sep_out[product_url] = img
                    else:
                        sep_out[norm_key] = img
                done += 1
                if args.verbose:
                    print(f"      -> {img[:60]}...")
            else:
                if args.verbose:
                    print("      -> no image")
            time.sleep(args.delay)
            if (idx + 1) % 50 == 0:
                save()
                print(f"  [checkpoint] Saved: cosmetics {len(cos_out)}, sephora {len(sep_out)}")
        save()
        print(f"\n[OK] Done. Saved: cosmetics {len(cos_out)}, sephora {len(sep_out)} (+{done} new)")
    except KeyboardInterrupt:
        save()
        print(f"\n[Ctrl+C] Saved: cosmetics {len(cos_out)}, sephora {len(sep_out)} (+{done} new)")
        raise


if __name__ == "__main__":
    main()
